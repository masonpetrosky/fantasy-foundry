from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.core.projections_export import (
    apply_calculator_overlay_values,
    default_projection_export_columns,
    normalize_sort_dir,
    parse_export_columns,
    sort_projection_rows,
    validate_sort_col,
)


def _value_col_sort_key(col: str) -> tuple[int, int | str]:
    suffix = col.split("_", 1)[1] if "_" in col else col
    return (0, int(suffix)) if str(suffix).isdigit() else (1, suffix)


def test_parse_export_columns_deduplicates_and_trims_tokens() -> None:
    assert parse_export_columns(" Player , Team,Player, ,DynastyValue ") == ["Player", "Team", "DynastyValue"]


def test_default_projection_export_columns_prefers_core_identity_and_dynasty_cols() -> None:
    rows = [
        {
            "Player": "A",
            "Team": "SEA",
            "Pos": "OF",
            "Age": 24,
            "DynastyValue": 1.2,
            "AB": 100,
            "R": 20,
            "HR": 10,
            "RBI": 25,
            "SB": 5,
            "AVG": 0.28,
            "OPS": 0.82,
            "Value_2026": 0.5,
            "Value_2027": 0.6,
            "OldestProjectionDate": "2025-12-01",
            "Years": "2026-2027",
        }
    ]
    cols = default_projection_export_columns(
        rows,
        dataset="bat",
        career_totals=True,
        hitter_core_export_cols=("AB", "R", "HR", "RBI", "SB", "AVG", "OPS"),
        pitcher_core_export_cols=("IP", "W", "K", "SV", "ERA", "WHIP", "QS", "QA3"),
        value_col_sort_key_fn=_value_col_sort_key,
    )
    assert cols[:5] == ["Player", "Team", "Pos", "Age", "DynastyValue"]
    assert "Value_2026" in cols
    assert "Value_2027" in cols
    assert "Years" in cols


def test_validate_sort_col_accepts_allowed_values_and_rejects_unknown() -> None:
    allowed = frozenset({"Player", "Team", "DynastyValue"})
    assert (
        validate_sort_col(
            "DynastyValue",
            dataset="all",
            normalize_filter_value_fn=lambda value: str(value or "").strip(),
            sortable_columns_for_dataset_fn=lambda _dataset: allowed,
        )
        == "DynastyValue"
    )

    with pytest.raises(HTTPException):
        validate_sort_col(
            "UnknownColumn",
            dataset="all",
            normalize_filter_value_fn=lambda value: str(value or "").strip(),
            sortable_columns_for_dataset_fn=lambda _dataset: allowed,
        )


def test_sort_projection_rows_orders_numeric_and_applies_deterministic_tiebreakers() -> None:
    rows = [
        {"Player": "B", "Team": "SEA", "Year": 2026, "DynastyValue": 2.0, "PlayerKey": "b", "PlayerEntityKey": "b"},
        {"Player": "A", "Team": "SEA", "Year": 2026, "DynastyValue": 2.0, "PlayerKey": "a", "PlayerEntityKey": "a"},
        {"Player": "C", "Team": "SEA", "Year": 2026, "DynastyValue": 1.0, "PlayerKey": "c", "PlayerEntityKey": "c"},
    ]
    out = sort_projection_rows(
        rows,
        sort_col="DynastyValue",
        sort_dir="desc",
        projection_text_sort_cols={"Player", "Team", "Pos", "Type", "Years"},
        player_key_col="PlayerKey",
        player_entity_key_col="PlayerEntityKey",
    )
    assert [row["Player"] for row in out] == ["A", "B", "C"]


def test_sort_projection_rows_handles_oldest_projection_date_ascending() -> None:
    rows = [
        {"Player": "A", "OldestProjectionDate": "2025-12-31", "PlayerKey": "a", "PlayerEntityKey": "a"},
        {"Player": "B", "OldestProjectionDate": "2025-11-30", "PlayerKey": "b", "PlayerEntityKey": "b"},
    ]
    out = sort_projection_rows(
        rows,
        sort_col="OldestProjectionDate",
        sort_dir="asc",
        projection_text_sort_cols={"Player", "Team", "Pos", "Type", "Years"},
        player_key_col="PlayerKey",
        player_entity_key_col="PlayerEntityKey",
    )
    assert [row["Player"] for row in out] == ["B", "A"]


def test_apply_calculator_overlay_values_applies_overlay_only_when_enabled() -> None:
    rows = [{"PlayerEntityKey": "a", "DynastyValue": 1.0}, {"PlayerEntityKey": "b", "DynastyValue": 2.0}]
    overlay_by_job = {"job-1": {"a": {"DynastyValue": 9.0, "Value_2026": 8.0}}}

    out = apply_calculator_overlay_values(
        rows,
        include_dynasty=True,
        calculator_job_id="job-1",
        normalize_filter_value_fn=lambda value: str(value or "").strip(),
        calculator_overlay_values_for_job_fn=lambda job_id: overlay_by_job.get(str(job_id), {}),
        row_overlay_lookup_key_fn=lambda row: str(row.get("PlayerEntityKey") or "").strip(),
    )
    assert out[0]["DynastyValue"] == 9.0
    assert out[0]["Value_2026"] == 8.0
    assert out[1]["DynastyValue"] == 2.0


def test_normalize_sort_dir_defaults_to_desc() -> None:
    assert normalize_sort_dir("asc") == "asc"
    assert normalize_sort_dir(None) == "desc"
