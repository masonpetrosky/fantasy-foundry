from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

import backend.dynasty_roto_values as dynasty_roto_values
from backend.valuation import league_math
from backend.valuation.models import LeagueSettings


def test_wrapper_league_hitter_components_delegates() -> None:
    df = pd.DataFrame([{"H": 1.0, "2B": 0.0, "3B": 0.0, "HR": 0.0, "BB": 0.0, "HBP": 0.0, "AB": 1.0, "SF": 0.0}])
    sentinel = object()
    with patch.object(league_math, "league_hitter_components", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_hitter_components(df)
    mocked.assert_called_once_with(df)
    assert result is sentinel


def test_wrapper_league_ensure_pitch_cols_delegates() -> None:
    df = pd.DataFrame([{"SV": 1.0, "HLD": 1.0}])
    sentinel = object()
    with patch.object(league_math, "league_ensure_pitch_cols", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_ensure_pitch_cols(df)
    mocked.assert_called_once_with(df)
    assert result is sentinel


def test_wrapper_league_zscore_delegates() -> None:
    s = pd.Series([1.0, 2.0, 3.0])
    sentinel = object()
    with patch.object(league_math, "league_zscore", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_zscore(s)
    mocked.assert_called_once_with(s)
    assert result is sentinel


def test_wrapper_league_initial_hitter_weight_delegates() -> None:
    df = pd.DataFrame([{"AB": 1.0, "H": 1.0, "R": 1.0, "HR": 1.0, "RBI": 1.0, "SB": 1.0, "OPS": 1.0}])
    sentinel = object()
    with patch.object(league_math, "league_initial_hitter_weight", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_initial_hitter_weight(df)
    mocked.assert_called_once_with(df)
    assert result is sentinel


def test_wrapper_league_initial_pitcher_weight_delegates() -> None:
    df = pd.DataFrame([{"IP": 1.0, "ER": 1.0, "H": 1.0, "BB": 1.0, "ERA": 1.0, "WHIP": 1.0, "W": 1.0, "K": 1.0, "SVH": 1.0, "QA3": 1.0}])
    sentinel = object()
    with patch.object(league_math, "league_initial_pitcher_weight", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_initial_pitcher_weight(df)
    mocked.assert_called_once_with(df)
    assert result is sentinel


def test_wrapper_league_team_avg_ops_delegates() -> None:
    series = pd.Series({"AB": 10.0, "H": 3.0, "TB": 5.0, "OBP_num": 4.0, "OBP_den": 12.0})
    sentinel = object()
    with patch.object(league_math, "league_team_avg_ops", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_team_avg_ops(series)
    mocked.assert_called_once_with(series)
    assert result is sentinel


def test_wrapper_league_replacement_pitcher_rates_delegates() -> None:
    all_pit = pd.DataFrame([{"Player": "A", "weight": 1.0, "IP": 1.0, "W": 0.0, "K": 0.0, "SVH": 0.0, "QA3": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0}])
    assigned = pd.DataFrame([{"Player": "A"}])
    sentinel = object()
    with patch.object(league_math, "league_replacement_pitcher_rates", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_replacement_pitcher_rates(all_pit, assigned, n_rep=25)
    mocked.assert_called_once_with(all_pit, assigned, n_rep=25)
    assert result is sentinel


def test_wrapper_league_apply_ip_cap_delegates() -> None:
    totals = {"IP": 100.0}
    sentinel = object()
    with patch.object(league_math, "league_apply_ip_cap", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_apply_ip_cap(totals, ip_cap=150.0, rep_rates={"W": 0.1})
    mocked.assert_called_once_with(totals, ip_cap=150.0, rep_rates={"W": 0.1})
    assert result is sentinel


def test_wrapper_league_simulate_sgp_hit_delegates() -> None:
    assigned_hit = pd.DataFrame([{"AssignedSlot": "OF"}])
    lg = LeagueSettings()
    rng = np.random.default_rng(1)
    sentinel = object()
    with patch.object(league_math, "league_simulate_sgp_hit", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_simulate_sgp_hit(assigned_hit, lg, rng)
    mocked.assert_called_once_with(assigned_hit, lg, rng)
    assert result is sentinel


def test_wrapper_league_simulate_sgp_pit_delegates() -> None:
    assigned_pit = pd.DataFrame([{"AssignedSlot": "SP"}])
    lg = LeagueSettings()
    rng = np.random.default_rng(2)
    rates = {"W": 0.0, "K": 0.0, "SVH": 0.0, "QA3": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0}
    sentinel = object()
    with patch.object(league_math, "league_simulate_sgp_pit", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_simulate_sgp_pit(assigned_pit, lg, rates, rng)
    mocked.assert_called_once_with(assigned_pit, lg, rates, rng)
    assert result is sentinel


def test_wrapper_league_sum_slots_delegates() -> None:
    baseline = pd.DataFrame([{"AssignedSlot": "OF", "R": 1.0}]).set_index("AssignedSlot")
    sentinel = object()
    with patch.object(league_math, "league_sum_slots", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_sum_slots(baseline, ["OF"])
    mocked.assert_called_once_with(baseline, ["OF"])
    assert result is sentinel


def test_wrapper_league_compute_year_context_delegates() -> None:
    bat = pd.DataFrame([{"Year": 2026, "AB": 1.0}])
    pit = pd.DataFrame([{"Year": 2026, "IP": 1.0}])
    lg = LeagueSettings()
    sentinel = object()
    with patch.object(league_math, "league_compute_year_context", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_compute_year_context(2026, bat, pit, lg, rng_seed=9)
    mocked.assert_called_once_with(2026, bat, pit, lg, 9)
    assert result is sentinel


def test_wrapper_league_compute_year_player_values_delegates() -> None:
    ctx = {"year": 2026}
    lg = LeagueSettings()
    sentinel = object()
    with patch.object(league_math, "league_compute_year_player_values", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_compute_year_player_values(ctx, lg)
    mocked.assert_called_once_with(ctx, lg)
    assert result is sentinel


def test_wrapper_league_compute_replacement_baselines_delegates() -> None:
    ctx = {"year": 2026}
    lg = LeagueSettings()
    sentinel = object()
    with patch.object(league_math, "league_compute_replacement_baselines", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_compute_replacement_baselines(
            ctx,
            lg,
            rostered_players={"A", "B"},
            n_repl=4,
        )
    mocked.assert_called_once_with(
        ctx,
        lg,
        rostered_players={"A", "B"},
        n_repl=4,
    )
    assert result is sentinel


def test_wrapper_league_compute_year_player_values_vs_replacement_delegates() -> None:
    ctx = {"year": 2026}
    lg = LeagueSettings()
    repl_hit = pd.DataFrame([{"AssignedSlot": "OF"}]).set_index("AssignedSlot")
    repl_pit = pd.DataFrame([{"AssignedSlot": "SP"}]).set_index("AssignedSlot")
    sentinel = object()
    with patch.object(league_math, "league_compute_year_player_values_vs_replacement", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_compute_year_player_values_vs_replacement(
            ctx,
            lg,
            repl_hit,
            repl_pit,
        )
    mocked.assert_called_once_with(
        ctx,
        lg,
        repl_hit=repl_hit,
        repl_pit=repl_pit,
    )
    assert result is sentinel


def test_wrapper_league_combine_hitter_pitcher_year_delegates() -> None:
    hit_vals = pd.DataFrame([{"Player": "A", "Year": 2026, "YearValue": 1.0, "BestSlot": "OF", "Pos": "OF", "MLBTeam": "AAA", "Age": 25}])
    pit_vals = pd.DataFrame([{"Player": "A", "Year": 2026, "YearValue": 2.0, "BestSlot": "SP", "Pos": "SP", "MLBTeam": "AAA", "Age": 25}])
    sentinel = object()
    with patch.object(league_math, "league_combine_hitter_pitcher_year", return_value=sentinel) as mocked:
        result = dynasty_roto_values.league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way="max")
    mocked.assert_called_once_with(hit_vals, pit_vals, "max")
    assert result is sentinel
