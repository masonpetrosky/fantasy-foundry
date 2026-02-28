"""Projection export/sort/overlay helpers."""

from __future__ import annotations

from functools import cmp_to_key
from typing import Callable, Literal

import pandas as pd
from fastapi import HTTPException


def normalize_sort_dir(value: str | None) -> Literal["asc", "desc"]:
    return "asc" if str(value or "").strip().lower() == "asc" else "desc"


def ordered_unique(cols: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for col in cols:
        name = str(col or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def parse_export_columns(value: str | None) -> list[str]:
    if not value:
        return []
    tokens = [token.strip() for token in str(value).split(",")]
    return ordered_unique([token for token in tokens if token])


def default_projection_export_columns(
    rows: list[dict],
    *,
    dataset: str,
    career_totals: bool,
    hitter_core_export_cols: tuple[str, ...],
    pitcher_core_export_cols: tuple[str, ...],
    value_col_sort_key_fn: Callable[[str], tuple[int, int | str]],
) -> list[str]:
    available = ordered_unique([str(key) for row in rows if isinstance(row, dict) for key in row.keys()])
    if not available:
        return ["Player", "Team", "Pos", "Age", "DynastyValue"]

    available_set = set(available)
    season_col = "Years" if career_totals else "Year"
    dynasty_cols = sorted(
        [col for col in available if col.startswith("Value_")],
        key=value_col_sort_key_fn,
    )
    identity_cols = ["Player", "Team", "Pos", "Age", "DynastyValue"]

    if dataset == "bat":
        desired = ordered_unique(
            [
                *identity_cols,
                *hitter_core_export_cols,
                *dynasty_cols,
                "OBP",
                "G",
                "H",
                "2B",
                "3B",
                "BB",
                "SO",
                "OldestProjectionDate",
                season_col,
            ]
        )
    elif dataset == "pitch":
        desired = ordered_unique(
            [
                *identity_cols,
                *pitcher_core_export_cols,
                *dynasty_cols,
                "G",
                "GS",
                "L",
                "BB",
                "H",
                "HR",
                "ER",
                "SVH",
                "OldestProjectionDate",
                season_col,
            ]
        )
    else:
        desired = ordered_unique(
            [
                *identity_cols,
                *hitter_core_export_cols,
                *pitcher_core_export_cols,
                *dynasty_cols,
                "OBP",
                "G",
                "H",
                "2B",
                "3B",
                "BB",
                "SO",
                "GS",
                "L",
                "PitBB",
                "PitH",
                "PitHR",
                "ER",
                "SVH",
                "OldestProjectionDate",
                season_col,
                "Type",
            ]
        )

    return [col for col in desired if col in available_set]


def validate_sort_col(
    sort_col: str | None,
    *,
    dataset: str,
    normalize_filter_value_fn: Callable[[str | None], str],
    sortable_columns_for_dataset_fn: Callable[[str], frozenset[str]],
) -> str | None:
    normalized = normalize_filter_value_fn(sort_col)
    if not normalized:
        return None
    allowed = sortable_columns_for_dataset_fn(dataset)
    if normalized not in allowed:
        sample = ", ".join(sorted(list(allowed))[:20])
        raise HTTPException(
            status_code=422,
            detail=f"sort_col '{normalized}' is not supported for {dataset}. Example valid columns: {sample}",
        )
    return normalized


def sort_projection_rows(
    rows: list[dict],
    sort_col: str | None,
    sort_dir: str | None,
    *,
    projection_text_sort_cols: set[str],
    player_key_col: str,
    player_entity_key_col: str,
) -> list[dict]:
    col = str(sort_col or "").strip()
    if not col:
        return rows

    direction = normalize_sort_dir(sort_dir)
    text_cols = projection_text_sort_cols | {
        player_key_col,
        player_entity_key_col,
        "DynastyMatchStatus",
    }

    def _cmp_for_col(a: dict, b: dict, compare_col: str, compare_dir: Literal["asc", "desc"]) -> int:
        av = a.get(compare_col)
        bv = b.get(compare_col)

        if compare_col == "OldestProjectionDate":
            av_ts = pd.to_datetime(av, errors="coerce")
            bv_ts = pd.to_datetime(bv, errors="coerce")
            av_missing = pd.isna(av_ts)
            bv_missing = pd.isna(bv_ts)
            if av_missing and bv_missing:
                return 0
            if av_missing:
                return 1
            if bv_missing:
                return -1
            av_num = float(av_ts.value)
            bv_num = float(bv_ts.value)
            if av_num == bv_num:
                return 0
            cmp = -1 if av_num < bv_num else 1
            return cmp if compare_dir == "asc" else -cmp

        if compare_col in text_cols:
            av_text = str(av or "").strip()
            bv_text = str(bv or "").strip()
            if not av_text and not bv_text:
                return 0
            if not av_text:
                return 1
            if not bv_text:
                return -1
            av_norm = av_text.casefold()
            bv_norm = bv_text.casefold()
            if av_norm == bv_norm:
                return 0
            cmp = -1 if av_norm < bv_norm else 1
            return cmp if compare_dir == "asc" else -cmp

        try:
            av_num = float(av)
        except (TypeError, ValueError):
            av_num = float("-inf")
        try:
            bv_num = float(bv)
        except (TypeError, ValueError):
            bv_num = float("-inf")
        if pd.isna(av_num):
            av_num = float("-inf")
        if pd.isna(bv_num):
            bv_num = float("-inf")
        if av_num == bv_num:
            return 0
        cmp = -1 if av_num < bv_num else 1
        return cmp if compare_dir == "asc" else -cmp

    def _cmp(a: dict, b: dict) -> int:
        primary = _cmp_for_col(a, b, col, direction)
        if primary != 0:
            return primary
        for tie_col in (player_entity_key_col, "Player", "Year", "Team"):
            tie_result = _cmp_for_col(a, b, tie_col, "asc")
            if tie_result != 0:
                return tie_result
        return 0

    return sorted(rows, key=cmp_to_key(_cmp))


def apply_calculator_overlay_values(
    rows: list[dict],
    *,
    include_dynasty: bool,
    calculator_job_id: str | None,
    normalize_filter_value_fn: Callable[[str | None], str],
    calculator_overlay_values_for_job_fn: Callable[[str | None], dict[str, dict]],
    row_overlay_lookup_key_fn: Callable[[dict], str],
) -> list[dict]:
    if not include_dynasty or not rows:
        return rows

    job_id = normalize_filter_value_fn(calculator_job_id)
    if not job_id:
        return rows

    overlay_by_key = calculator_overlay_values_for_job_fn(job_id)
    if not overlay_by_key or not isinstance(overlay_by_key, dict):
        return rows

    next_rows: list[dict] = []
    changed = False
    for row in rows:
        key = row_overlay_lookup_key_fn(row)
        overlay = overlay_by_key.get(key) if key else None
        if overlay and isinstance(overlay, dict):
            next_rows.append({**row, **overlay})
            changed = True
        else:
            next_rows.append(row)
    return next_rows if changed else rows
