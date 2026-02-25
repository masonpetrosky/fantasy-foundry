from __future__ import annotations

import pandas as pd

from backend import dynasty_roto_values
from backend.valuation import projection_averaging


def test_wrapper_derived_rate_constants_alias_extracted_module() -> None:
    assert dynasty_roto_values.DERIVED_HIT_RATE_COLS == projection_averaging.DERIVED_HIT_RATE_COLS
    assert dynasty_roto_values.DERIVED_PIT_RATE_COLS == projection_averaging.DERIVED_PIT_RATE_COLS


def test_wrapper_average_recent_projections_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}
    frame = pd.DataFrame([{"Player": "A", "Year": 2026, "AB": 100}])
    expected = pd.DataFrame([{"Player": "A", "Year": 2026, "AB": 100, "ProjectionsUsed": 1}])

    def fake_average(
        df: pd.DataFrame,
        stat_cols: list[str],
        group_cols: list[str] | None = None,
        max_entries: int = 3,
    ) -> pd.DataFrame:
        calls["args"] = (df, stat_cols, group_cols, max_entries)
        return expected

    monkeypatch.setattr(projection_averaging, "average_recent_projections", fake_average)
    out = dynasty_roto_values.average_recent_projections(
        frame,
        stat_cols=["AB"],
        group_cols=["Player", "Year"],
        max_entries=5,
    )

    assert calls["args"] == (frame, ["AB"], ["Player", "Year"], 5)
    assert out is expected


def test_wrapper_projection_meta_for_start_year_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}
    bat = pd.DataFrame([{"Player": "A"}])
    pit = pd.DataFrame([{"Player": "A"}])
    expected = pd.DataFrame([{"Player": "A", "ProjectionsUsed": 2}])

    def fake_projection_meta(bat_df: pd.DataFrame, pit_df: pd.DataFrame, start_year: int) -> pd.DataFrame:
        calls["args"] = (bat_df, pit_df, start_year)
        return expected

    monkeypatch.setattr(projection_averaging, "projection_meta_for_start_year", fake_projection_meta)
    out = dynasty_roto_values.projection_meta_for_start_year(bat, pit, 2026)

    assert calls["args"] == (bat, pit, 2026)
    assert out is expected


def test_wrapper_numeric_stat_cols_for_recent_avg_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}
    frame = pd.DataFrame([{"Player": "A", "Year": 2026, "AB": 100}])

    def fake_numeric(
        df: pd.DataFrame,
        group_cols: list[str] | None = None,
        exclude_cols: set[str] | None = None,
    ) -> list[str]:
        calls["args"] = (df, group_cols, exclude_cols)
        return ["AB"]

    monkeypatch.setattr(projection_averaging, "numeric_stat_cols_for_recent_avg", fake_numeric)
    out = dynasty_roto_values.numeric_stat_cols_for_recent_avg(
        frame,
        group_cols=["Player", "Year"],
        exclude_cols={"Age"},
    )

    assert calls["args"] == (frame, ["Player", "Year"], {"Age"})
    assert out == ["AB"]


def test_wrapper_reorder_detail_columns_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}
    frame = pd.DataFrame([{"Player": "A", "Year": 2026}])
    expected = pd.DataFrame([{"Year": 2026, "Player": "A"}])

    def fake_reorder(
        df: pd.DataFrame,
        input_cols: list[str],
        add_after: str | None = None,
        extra_cols: list[str] | None = None,
    ) -> pd.DataFrame:
        calls["args"] = (df, input_cols, add_after, extra_cols)
        return expected

    monkeypatch.setattr(projection_averaging, "reorder_detail_columns", fake_reorder)
    out = dynasty_roto_values.reorder_detail_columns(
        frame,
        input_cols=["Player", "Year"],
        add_after="Player",
        extra_cols=["DynastyValue"],
    )

    assert calls["args"] == (frame, ["Player", "Year"], "Player", ["DynastyValue"])
    assert out is expected
