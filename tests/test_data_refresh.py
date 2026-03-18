from __future__ import annotations

import json
import threading
from pathlib import Path

from backend.core import data_refresh


class _Stringable:
    def __str__(self) -> str:
        return "stringable-value"


def _value_col_sort_key(col: str) -> tuple[int, int | str]:
    suffix = col.split("_", 1)[1] if "_" in col else col
    return (0, int(suffix)) if str(suffix).isdigit() else (1, suffix)


def test_path_signature_for_existing_and_missing_paths(tmp_path: Path) -> None:
    existing = tmp_path / "bat.json"
    existing.write_text('{"ok":true}')

    existing_sig = data_refresh.path_signature(existing)
    missing_sig = data_refresh.path_signature(tmp_path / "missing.json")

    assert existing_sig[0] == str(existing)
    assert isinstance(existing_sig[1], int)
    assert existing_sig[2] == len('{"ok":true}')
    assert missing_sig == (str(tmp_path / "missing.json"), None, None)


def test_compute_data_signature_preserves_input_order(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    a.write_text("A")
    b.write_text("B")

    signature = data_refresh.compute_data_signature((a, b))

    assert signature[0][0] == str(a)
    assert signature[1][0] == str(b)
    assert len(signature) == 2


def test_stable_data_version_path_label_uses_basename_only() -> None:
    assert data_refresh.stable_data_version_path_label(Path("/tmp/somewhere/pitch.json")) == "pitch.json"


def test_compute_content_data_version_is_stable_and_sensitive_to_name_and_content(tmp_path: Path) -> None:
    one = tmp_path / "one.json"
    one.write_text('{"value":1}')
    missing = tmp_path / "missing.json"

    version_before = data_refresh.compute_content_data_version((one, missing))
    version_same = data_refresh.compute_content_data_version((one, missing))
    assert version_before == version_same

    one.write_text('{"value":2}')
    version_after_content_change = data_refresh.compute_content_data_version((one, missing))
    assert version_after_content_change != version_before

    renamed = tmp_path / "renamed.json"
    renamed.write_text('{"value":2}')
    version_after_name_change = data_refresh.compute_content_data_version((renamed, missing))
    assert version_after_name_change != version_after_content_change


def test_coerce_serialized_dynasty_lookup_map_returns_empty_for_non_dict() -> None:
    assert data_refresh.coerce_serialized_dynasty_lookup_map([]) == {}


def test_coerce_serialized_dynasty_lookup_map_normalizes_keys_and_values() -> None:
    raw = {
        " player-a ": {
            "Value_2026": 12.3,
            "BOOL": True,
            "none-value": None,
            "nan-value": float("nan"),
            "obj-value": _Stringable(),
            "": "ignored",
        },
        "": {"Value_2026": 1},
        "player-b": "not-a-map",
    }

    cleaned = data_refresh.coerce_serialized_dynasty_lookup_map(raw)

    assert set(cleaned) == {"player-a"}
    assert cleaned["player-a"]["Value_2026"] == 12.3
    assert cleaned["player-a"]["BOOL"] is True
    assert cleaned["player-a"]["none-value"] is None
    assert cleaned["player-a"]["nan-value"] is None
    assert cleaned["player-a"]["obj-value"] == "stringable-value"
    assert "" not in cleaned["player-a"]


def test_dynasty_lookup_payload_version_prefers_cache_data_version() -> None:
    assert (
        data_refresh.dynasty_lookup_payload_version(
            {"cache_data_version": "new", "data_version": "legacy"}
        )
        == "new"
    )
    assert data_refresh.dynasty_lookup_payload_version({"data_version": "legacy"}) == "legacy"
    assert data_refresh.dynasty_lookup_payload_version({"data_version": "  "}) is None


def test_inspect_precomputed_default_dynasty_lookup_reports_disabled_for_pytest_mode(tmp_path: Path) -> None:
    result = data_refresh.inspect_precomputed_default_dynasty_lookup(
        current_data_version="v1",
        dynasty_lookup_cache_path=tmp_path / "dynasty_lookup.json",
        pytest_current_test=True,
        value_col_sort_key=_value_col_sort_key,
    )

    assert result.status == "disabled"
    assert result.expected_version == "v1"


def test_inspect_precomputed_default_dynasty_lookup_reports_missing_file(tmp_path: Path) -> None:
    result = data_refresh.inspect_precomputed_default_dynasty_lookup(
        current_data_version="v1",
        dynasty_lookup_cache_path=tmp_path / "dynasty_lookup.json",
        pytest_current_test=False,
        value_col_sort_key=_value_col_sort_key,
    )

    assert result.status == "missing"


def test_inspect_precomputed_default_dynasty_lookup_reports_invalid_json(tmp_path: Path) -> None:
    cache_path = tmp_path / "dynasty_lookup.json"
    cache_path.write_text("{invalid-json")

    result = data_refresh.inspect_precomputed_default_dynasty_lookup(
        current_data_version="v1",
        dynasty_lookup_cache_path=cache_path,
        pytest_current_test=False,
        value_col_sort_key=_value_col_sort_key,
    )

    assert result.status == "invalid"
    assert "Failed to parse dynasty_lookup.json" in str(result.error)


def test_inspect_precomputed_default_dynasty_lookup_requires_json_object_payload(tmp_path: Path) -> None:
    cache_path = tmp_path / "dynasty_lookup.json"
    cache_path.write_text(json.dumps([1, 2, 3]))

    result = data_refresh.inspect_precomputed_default_dynasty_lookup(
        current_data_version="v1",
        dynasty_lookup_cache_path=cache_path,
        pytest_current_test=False,
        value_col_sort_key=_value_col_sort_key,
    )

    assert result.status == "invalid"
    assert "payload is not a JSON object" in str(result.error)


def test_inspect_precomputed_default_dynasty_lookup_reports_stale_versions(tmp_path: Path) -> None:
    cache_path = tmp_path / "dynasty_lookup.json"
    cache_path.write_text(json.dumps({"cache_data_version": "old-version"}))

    result = data_refresh.inspect_precomputed_default_dynasty_lookup(
        current_data_version="new-version",
        dynasty_lookup_cache_path=cache_path,
        pytest_current_test=False,
        value_col_sort_key=_value_col_sort_key,
    )

    assert result.status == "stale"
    assert result.expected_version == "new-version"
    assert result.found_version == "old-version"


def test_inspect_precomputed_default_dynasty_lookup_requires_non_empty_lookup_maps(tmp_path: Path) -> None:
    cache_path = tmp_path / "dynasty_lookup.json"
    cache_path.write_text(json.dumps({"cache_data_version": "v1"}))

    result = data_refresh.inspect_precomputed_default_dynasty_lookup(
        current_data_version="v1",
        dynasty_lookup_cache_path=cache_path,
        pytest_current_test=False,
        value_col_sort_key=_value_col_sort_key,
    )

    assert result.status == "invalid"
    assert "contains no usable lookup maps" in str(result.error)


def test_inspect_precomputed_default_dynasty_lookup_returns_ready_payload(tmp_path: Path) -> None:
    cache_path = tmp_path / "dynasty_lookup.json"
    cache_path.write_text(
        json.dumps(
            {
                "cache_data_version": "v1",
                "lookup_by_entity": {" entity-a ": {"Value_2027": 1.2}},
                "lookup_by_player_key": {" player-a ": {"Value_2026": 2.3}},
                "ambiguous_player_keys": ["player-a", "", None, " player-b "],
                "year_cols": ["Value_2030", "Value_2027", "not-a-year", 1],
            }
        )
    )

    result = data_refresh.inspect_precomputed_default_dynasty_lookup(
        current_data_version="v1",
        dynasty_lookup_cache_path=cache_path,
        pytest_current_test=False,
        value_col_sort_key=_value_col_sort_key,
    )

    assert result.status == "ready"
    assert result.found_version == "v1"
    assert result.lookup is not None
    by_entity, by_player_key, ambiguous, year_cols = result.lookup
    assert set(by_entity) == {"entity-a"}
    assert set(by_player_key) == {"player-a"}
    assert ambiguous == {"player-a", "player-b"}
    assert year_cols == ["Value_2027", "Value_2030"]


def test_reload_projection_data_loads_all_inputs_and_builds_averages() -> None:
    loaded_names: list[str] = []
    average_calls: list[tuple[bool, int]] = []

    def load_json(name: str):
        loaded_names.append(name)
        payloads = {
            "meta.json": {"years": [2026]},
            "bat.json": [{"Player": "Hitter", "Year": 2026}],
            "pitch.json": [{"Player": "Pitcher", "Year": 2026}],
        }
        return payloads[name]

    def with_player_identity_keys(bat_rows: list[dict], pit_rows: list[dict]):
        return (
            [dict(bat_rows[0], PlayerKey="hitter-key")],
            [dict(pit_rows[0], PlayerKey="pitcher-key")],
        )

    def average_recent_projection_rows(rows: list[dict], *, is_hitter: bool):
        average_calls.append((is_hitter,))
        return rows

    def projection_freshness_payload(bat_rows: list[dict], pit_rows: list[dict]):
        return {"bat_count": len(bat_rows), "pit_count": len(pit_rows)}

    result = data_refresh.reload_projection_data(
        load_json=load_json,
        with_player_identity_keys=with_player_identity_keys,
        average_recent_projection_rows=average_recent_projection_rows,
        projection_freshness_payload=projection_freshness_payload,
    )

    meta, bat_raw, pit_raw, bat_avg, pit_avg, freshness = result
    assert meta == {"years": [2026]}
    assert loaded_names == ["meta.json", "bat.json", "pitch.json"]
    assert average_calls == [(True,), (False,)]
    assert bat_raw[0]["PlayerKey"] == "hitter-key"
    assert pit_raw[0]["PlayerKey"] == "pitcher-key"
    assert bat_avg == bat_raw
    assert pit_avg == pit_raw
    assert freshness == {"bat_count": 1, "pit_count": 1}


def test_refresh_data_if_needed_returns_none_when_signature_unchanged_pre_lock(tmp_path: Path) -> None:
    signatures = [(("meta.json", 1, 10),)]
    calls = {"reload": 0, "on_error": 0, "clear": 0, "version": 0}

    def compute_signature(_paths: tuple[Path, ...]):
        return signatures[0]

    result = data_refresh.refresh_data_if_needed(
        data_refresh_lock=threading.Lock(),
        data_refresh_paths=(tmp_path / "meta.json",),
        current_data_source_signature=signatures[0],
        compute_data_signature_fn=compute_signature,
        reload_projection_data_fn=lambda: calls.__setitem__("reload", calls["reload"] + 1),
        on_reload_exception=lambda: calls.__setitem__("on_error", calls["on_error"] + 1),
        clear_after_reload=lambda: calls.__setitem__("clear", calls["clear"] + 1),
        compute_content_data_version_fn=lambda _paths: calls.__setitem__("version", calls["version"] + 1) or "ver",
    )

    assert result is None
    assert calls == {"reload": 0, "on_error": 0, "clear": 0, "version": 0}


def test_refresh_data_if_needed_returns_none_when_signature_changes_then_reverts(tmp_path: Path) -> None:
    unchanged = (("meta.json", 1, 10),)
    changed = (("meta.json", 2, 10),)
    sequence = [changed, unchanged]
    calls = {"reload": 0}

    def compute_signature(_paths: tuple[Path, ...]):
        return sequence.pop(0)

    result = data_refresh.refresh_data_if_needed(
        data_refresh_lock=threading.Lock(),
        data_refresh_paths=(tmp_path / "meta.json",),
        current_data_source_signature=unchanged,
        compute_data_signature_fn=compute_signature,
        reload_projection_data_fn=lambda: calls.__setitem__("reload", calls["reload"] + 1),
        on_reload_exception=lambda: None,
        clear_after_reload=lambda: None,
        compute_content_data_version_fn=lambda _paths: "unused",
    )

    assert result is None
    assert calls["reload"] == 0


def test_refresh_data_if_needed_calls_error_hook_on_reload_exception(tmp_path: Path) -> None:
    changed = (("meta.json", 2, 10),)
    sequence = [changed, changed]
    state = {"on_error": 0, "clear": 0, "version": 0}

    def compute_signature(_paths: tuple[Path, ...]):
        return sequence.pop(0)

    def explode() -> None:
        raise OSError("reload failed")

    result = data_refresh.refresh_data_if_needed(
        data_refresh_lock=threading.Lock(),
        data_refresh_paths=(tmp_path / "meta.json",),
        current_data_source_signature=(("meta.json", 1, 10),),
        compute_data_signature_fn=compute_signature,
        reload_projection_data_fn=explode,
        on_reload_exception=lambda: state.__setitem__("on_error", state["on_error"] + 1),
        clear_after_reload=lambda: state.__setitem__("clear", state["clear"] + 1),
        compute_content_data_version_fn=lambda _paths: state.__setitem__("version", state["version"] + 1) or "unused",
    )

    assert result is None
    assert state == {"on_error": 1, "clear": 0, "version": 0}


def test_refresh_data_if_needed_returns_new_signature_and_content_version_after_success(tmp_path: Path) -> None:
    old = (("meta.json", 1, 10),)
    changed = (("meta.json", 2, 10),)
    sequence = [changed, changed]
    state = {"reload": 0, "clear": 0}

    def compute_signature(_paths: tuple[Path, ...]):
        return sequence.pop(0)

    result = data_refresh.refresh_data_if_needed(
        data_refresh_lock=threading.Lock(),
        data_refresh_paths=(tmp_path / "meta.json",),
        current_data_source_signature=old,
        compute_data_signature_fn=compute_signature,
        reload_projection_data_fn=lambda: state.__setitem__("reload", state["reload"] + 1),
        on_reload_exception=lambda: None,
        clear_after_reload=lambda: state.__setitem__("clear", state["clear"] + 1),
        compute_content_data_version_fn=lambda _paths: "content-v2",
    )

    assert result == (changed, "content-v2")
    assert state == {"reload": 1, "clear": 1}
