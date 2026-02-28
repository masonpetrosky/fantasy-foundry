"""Data refresh and precomputed dynasty lookup helpers."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def path_signature(path: Path) -> tuple[str, int | None, int | None]:
    try:
        stat = path.stat()
        return (str(path), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        return (str(path), None, None)


def compute_data_signature(paths: tuple[Path, ...]) -> tuple[tuple[str, int | None, int | None], ...]:
    return tuple(path_signature(path) for path in paths)


def stable_data_version_path_label(path: Path) -> str:
    # Content hash must be stable across environments, so avoid absolute paths.
    return path.name


def hash_file_into(path: Path, hasher: Any) -> None:
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)


def compute_content_data_version(paths: tuple[Path, ...]) -> str:
    hasher = hashlib.sha256()
    for path in paths:
        hasher.update(stable_data_version_path_label(path).encode("utf-8"))
        hasher.update(b"\x00")
        if not path.exists():
            hasher.update(b"__missing__")
            hasher.update(b"\x00")
            continue
        hash_file_into(path, hasher)
        hasher.update(b"\x00")
    return hasher.hexdigest()[:12]


def coerce_serialized_dynasty_lookup_map(raw: object) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}

    cleaned: dict[str, dict] = {}
    for raw_key, raw_values in raw.items():
        key = str(raw_key or "").strip()
        if not key or not isinstance(raw_values, dict):
            continue

        values: dict[str, object] = {}
        for raw_col, raw_value in raw_values.items():
            col = str(raw_col or "").strip()
            if not col:
                continue
            if raw_value is None:
                values[col] = None
                continue
            if isinstance(raw_value, bool):
                values[col] = bool(raw_value)
                continue
            if isinstance(raw_value, (int, float, str)):
                if isinstance(raw_value, float) and not math.isfinite(raw_value):
                    values[col] = None
                else:
                    values[col] = raw_value
                continue
            values[col] = str(raw_value)

        cleaned[key] = values

    return cleaned


def dynasty_lookup_payload_version(payload: dict[str, object]) -> str | None:
    cache_data_version = str(payload.get("cache_data_version") or "").strip()
    if cache_data_version:
        return cache_data_version
    legacy_data_version = str(payload.get("data_version") or "").strip()
    return legacy_data_version or None


@dataclass(frozen=True)
class LookupInspectionResult:
    status: str
    expected_version: str
    found_version: str | None = None
    lookup: tuple[dict[str, dict], dict[str, dict], set[str], list[str]] | None = None
    error: str | None = None


def inspect_precomputed_default_dynasty_lookup(
    *,
    current_data_version: str,
    dynasty_lookup_cache_path: Path,
    pytest_current_test: bool,
    value_col_sort_key: Callable[[str], tuple[int, int | str]],
) -> LookupInspectionResult:
    expected_version = current_data_version
    if pytest_current_test:
        return LookupInspectionResult(status="disabled", expected_version=expected_version)
    if not dynasty_lookup_cache_path.exists():
        return LookupInspectionResult(status="missing", expected_version=expected_version)

    try:
        payload = json.loads(dynasty_lookup_cache_path.read_text())
    except Exception as exc:
        return LookupInspectionResult(
            status="invalid",
            expected_version=expected_version,
            error=f"Failed to parse {dynasty_lookup_cache_path.name}: {exc}",
        )

    if not isinstance(payload, dict):
        return LookupInspectionResult(
            status="invalid",
            expected_version=expected_version,
            error=f"{dynasty_lookup_cache_path.name} payload is not a JSON object.",
        )

    payload_version = dynasty_lookup_payload_version(payload)
    if not payload_version or payload_version != expected_version:
        return LookupInspectionResult(
            status="stale",
            expected_version=expected_version,
            found_version=payload_version,
        )

    lookup_by_entity = coerce_serialized_dynasty_lookup_map(payload.get("lookup_by_entity"))
    lookup_by_player_key = coerce_serialized_dynasty_lookup_map(payload.get("lookup_by_player_key"))
    if not lookup_by_entity and not lookup_by_player_key:
        return LookupInspectionResult(
            status="invalid",
            expected_version=expected_version,
            found_version=payload_version,
            error=f"{dynasty_lookup_cache_path.name} contains no usable lookup maps.",
        )

    raw_ambiguous = payload.get("ambiguous_player_keys")
    ambiguous_player_keys = {
        str(value or "").strip()
        for value in raw_ambiguous
        if str(value or "").strip()
    } if isinstance(raw_ambiguous, list) else set()

    raw_year_cols = payload.get("year_cols")
    year_cols = sorted(
        {
            str(col).strip()
            for col in raw_year_cols
            if isinstance(col, str) and str(col).strip().startswith("Value_")
        } if isinstance(raw_year_cols, list) else set(),
        key=value_col_sort_key,
    )

    return LookupInspectionResult(
        status="ready",
        expected_version=expected_version,
        found_version=payload_version,
        lookup=(lookup_by_entity, lookup_by_player_key, ambiguous_player_keys, year_cols),
    )


def reload_projection_data(
    *,
    load_json: Callable[[str], Any],
    with_player_identity_keys: Callable[[list[dict], list[dict]], tuple[list[dict], list[dict]]],
    average_recent_projection_rows: Callable[..., list[dict]],
    projection_freshness_payload: Callable[[list[dict], list[dict]], dict[str, Any]],
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], dict[str, Any]]:
    meta = load_json("meta.json")
    bat_data_raw = load_json("bat.json")
    pit_data_raw = load_json("pitch.json")
    bat_data_raw, pit_data_raw = with_player_identity_keys(bat_data_raw, pit_data_raw)
    bat_data = average_recent_projection_rows(bat_data_raw, is_hitter=True)
    pit_data = average_recent_projection_rows(pit_data_raw, is_hitter=False)
    projection_freshness = projection_freshness_payload(bat_data, pit_data)
    return meta, bat_data_raw, pit_data_raw, bat_data, pit_data, projection_freshness


def refresh_data_if_needed(
    *,
    data_refresh_lock: Any,
    data_refresh_paths: tuple[Path, ...],
    current_data_source_signature: tuple[tuple[str, int | None, int | None], ...] | None,
    compute_data_signature_fn: Callable[[tuple[Path, ...]], tuple[tuple[str, int | None, int | None], ...]],
    reload_projection_data_fn: Callable[[], None],
    on_reload_exception: Callable[[], None],
    clear_after_reload: Callable[[], None],
    compute_content_data_version_fn: Callable[[tuple[Path, ...]], str],
) -> tuple[tuple[tuple[str, int | None, int | None], ...], str] | None:
    current_signature = compute_data_signature_fn(data_refresh_paths)
    if current_signature == current_data_source_signature:
        return None

    with data_refresh_lock:
        current_signature = compute_data_signature_fn(data_refresh_paths)
        if current_signature == current_data_source_signature:
            return None

        try:
            reload_projection_data_fn()
        except Exception:
            on_reload_exception()
            return None

        clear_after_reload()
        content_version = compute_content_data_version_fn(data_refresh_paths)
        return current_signature, content_version
