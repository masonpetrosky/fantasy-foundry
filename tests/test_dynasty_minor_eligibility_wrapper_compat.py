from __future__ import annotations

from unittest.mock import patch

import pandas as pd

import backend.dynasty_roto_values as dynasty_roto_values
from backend.valuation import minor_eligibility
from backend.valuation.models import CommonDynastyRotoSettings


def test_wrapper_infer_minor_eligibility_by_year_delegates() -> None:
    bat = pd.DataFrame([{"Player": "A", "Year": 2026, "AB": 1.0, "Age": 20.0}])
    pit = pd.DataFrame(columns=["Player", "Year", "IP", "Age"])
    sentinel = object()
    with patch.object(minor_eligibility, "_infer_minor_eligibility_by_year", return_value=sentinel) as mocked:
        result = dynasty_roto_values._infer_minor_eligibility_by_year(
            bat,
            pit,
            years=[2026],
            hitter_usage_max=130,
            pitcher_usage_max=50,
            hitter_age_max=25,
            pitcher_age_max=26,
        )
    mocked.assert_called_once_with(
        bat,
        pit,
        years=[2026],
        hitter_usage_max=130,
        pitcher_usage_max=50,
        hitter_age_max=25,
        pitcher_age_max=26,
    )
    assert result is sentinel


def test_wrapper_infer_minor_eligible_delegates() -> None:
    bat = pd.DataFrame([{"Player": "A", "Year": 2026, "AB": 1.0, "Age": 20.0}])
    pit = pd.DataFrame(columns=["Player", "Year", "IP", "Age"])
    lg = CommonDynastyRotoSettings()
    sentinel = object()
    with patch.object(minor_eligibility, "infer_minor_eligible", return_value=sentinel) as mocked:
        result = dynasty_roto_values.infer_minor_eligible(bat, pit, lg, start_year=2026)
    mocked.assert_called_once_with(bat, pit, lg, 2026)
    assert result is sentinel


def test_wrapper_non_vacant_player_names_delegates() -> None:
    df = pd.DataFrame([{"Player": "A"}])
    sentinel = object()
    with patch.object(minor_eligibility, "_non_vacant_player_names", return_value=sentinel) as mocked:
        result = dynasty_roto_values._non_vacant_player_names(df)
    mocked.assert_called_once_with(df)
    assert result is sentinel


def test_wrapper_players_with_playing_time_delegates() -> None:
    bat = pd.DataFrame([{"Player": "A", "Year": 2026, "AB": 10.0}])
    pit = pd.DataFrame([{"Player": "B", "Year": 2026, "IP": 5.0}])
    sentinel = object()
    with patch.object(minor_eligibility, "_players_with_playing_time", return_value=sentinel) as mocked:
        result = dynasty_roto_values._players_with_playing_time(bat, pit, [2026])
    mocked.assert_called_once_with(bat, pit, [2026])
    assert result is sentinel


def test_wrapper_select_mlb_roster_with_active_floor_delegates() -> None:
    stash = pd.DataFrame([{"Player": "A", "StashScore": 1.0}])
    sentinel = object()
    with patch.object(minor_eligibility, "_select_mlb_roster_with_active_floor", return_value=sentinel) as mocked:
        result = dynasty_roto_values._select_mlb_roster_with_active_floor(
            stash,
            excluded_players={"B"},
            total_mlb_slots=5,
            active_floor_names={"A"},
        )
    mocked.assert_called_once_with(
        stash,
        excluded_players={"B"},
        total_mlb_slots=5,
        active_floor_names={"A"},
    )
    assert result is sentinel


def test_wrapper_estimate_bench_negative_penalty_delegates() -> None:
    ctx = {"assigned_hit": pd.DataFrame([{"Player": "A", "G": 100.0}])}
    lg = CommonDynastyRotoSettings()
    sentinel = object()
    with patch.object(minor_eligibility, "_estimate_bench_negative_penalty", return_value=sentinel) as mocked:
        result = dynasty_roto_values._estimate_bench_negative_penalty(ctx, lg)
    mocked.assert_called_once_with(ctx, lg)
    assert result is sentinel


def test_wrapper_bench_stash_round_penalty_delegates() -> None:
    sentinel = object()
    with patch.object(minor_eligibility, "_bench_stash_round_penalty", return_value=sentinel) as mocked:
        result = dynasty_roto_values._bench_stash_round_penalty(
            2,
            bench_slots=6,
            min_penalty=0.1,
            max_penalty=0.8,
            gamma=1.5,
        )
    mocked.assert_called_once_with(
        2,
        bench_slots=6,
        min_penalty=0.1,
        max_penalty=0.8,
        gamma=1.5,
    )
    assert result is sentinel


def test_wrapper_build_bench_stash_penalty_map_delegates() -> None:
    stash = pd.DataFrame([{"Player": "A", "StashScore": 1.0}])
    sentinel = object()
    with patch.object(minor_eligibility, "_build_bench_stash_penalty_map", return_value=sentinel) as mocked:
        result = dynasty_roto_values._build_bench_stash_penalty_map(
            stash,
            bench_stash_players={"A"},
            n_teams=2,
            bench_slots=3,
        )
    mocked.assert_called_once_with(
        stash,
        bench_stash_players={"A"},
        n_teams=2,
        bench_slots=3,
    )
    assert result is sentinel


def test_wrapper_apply_negative_value_stash_rules_delegates() -> None:
    sentinel = object()
    with patch.object(minor_eligibility, "_apply_negative_value_stash_rules", return_value=sentinel) as mocked:
        result = dynasty_roto_values._apply_negative_value_stash_rules(
            -3.0,
            can_minor_stash=False,
            can_bench_stash=True,
            bench_negative_penalty=0.25,
        )
    mocked.assert_called_once_with(
        -3.0,
        can_minor_stash=False,
        can_bench_stash=True,
        bench_negative_penalty=0.25,
    )
    assert result is sentinel


def test_wrapper_fillna_bool_delegates() -> None:
    series = pd.Series([True, None], dtype="boolean")
    sentinel = object()
    with patch.object(minor_eligibility, "_fillna_bool", return_value=sentinel) as mocked:
        result = dynasty_roto_values._fillna_bool(series, default=True)
    mocked.assert_called_once_with(series, default=True)
    assert result is sentinel


def test_wrapper_normalize_minor_eligibility_delegates() -> None:
    series = pd.Series(["yes", "no"])
    sentinel = object()
    with patch.object(minor_eligibility, "_normalize_minor_eligibility", return_value=sentinel) as mocked:
        result = dynasty_roto_values._normalize_minor_eligibility(series)
    mocked.assert_called_once_with(series)
    assert result is sentinel


def test_wrapper_minor_eligibility_by_year_from_input_delegates() -> None:
    bat = pd.DataFrame([{"Player": "A", "Year": 2026, "minor_eligible": True}])
    pit = pd.DataFrame(columns=["Player", "Year", "minor_eligible"])
    sentinel = object()
    with patch.object(minor_eligibility, "minor_eligibility_by_year_from_input", return_value=sentinel) as mocked:
        result = dynasty_roto_values.minor_eligibility_by_year_from_input(bat, pit)
    mocked.assert_called_once_with(bat, pit)
    assert result is sentinel


def test_wrapper_minor_eligibility_from_input_delegates() -> None:
    bat = pd.DataFrame([{"Player": "A", "Year": 2026, "minor_eligible": True}])
    pit = pd.DataFrame(columns=["Player", "Year", "minor_eligible"])
    sentinel = object()
    with patch.object(minor_eligibility, "minor_eligibility_from_input", return_value=sentinel) as mocked:
        result = dynasty_roto_values.minor_eligibility_from_input(bat, pit, start_year=2026)
    mocked.assert_called_once_with(bat, pit, 2026)
    assert result is sentinel


def test_wrapper_resolve_minor_eligibility_by_year_delegates() -> None:
    bat = pd.DataFrame([{"Player": "A", "Year": 2026, "AB": 1.0, "Age": 20.0}])
    pit = pd.DataFrame(columns=["Player", "Year", "IP", "Age"])
    sentinel = object()
    with patch.object(minor_eligibility, "_resolve_minor_eligibility_by_year", return_value=sentinel) as mocked:
        result = dynasty_roto_values._resolve_minor_eligibility_by_year(
            bat,
            pit,
            years=[2026],
            hitter_usage_max=130,
            pitcher_usage_max=50,
            hitter_age_max=25,
            pitcher_age_max=26,
        )
    mocked.assert_called_once_with(
        bat,
        pit,
        years=[2026],
        hitter_usage_max=130,
        pitcher_usage_max=50,
        hitter_age_max=25,
        pitcher_age_max=26,
    )
    assert result is sentinel
