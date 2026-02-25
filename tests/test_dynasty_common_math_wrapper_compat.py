from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

import backend.dynasty_roto_values as dynasty_roto_values
from backend.valuation import common_math
from backend.valuation.models import CommonDynastyRotoSettings


def test_wrapper_common_hit_category_totals_delegates() -> None:
    totals = {"R": 1.0}
    sentinel = object()
    with patch.object(common_math, "common_hit_category_totals", return_value=sentinel) as mocked:
        result = dynasty_roto_values.common_hit_category_totals(totals)
    mocked.assert_called_once_with(totals)
    assert result is sentinel


def test_wrapper_common_pitch_category_totals_delegates() -> None:
    totals = {"W": 1.0}
    sentinel = object()
    with patch.object(common_math, "common_pitch_category_totals", return_value=sentinel) as mocked:
        result = dynasty_roto_values.common_pitch_category_totals(totals)
    mocked.assert_called_once_with(totals)
    assert result is sentinel


def test_wrapper_common_replacement_pitcher_rates_delegates() -> None:
    all_pit = pd.DataFrame([{"Player": "A", "weight": 1.0, "IP": 1.0, "W": 1.0, "QS": 0.0, "QA3": 0.0, "K": 1.0, "SV": 0.0, "SVH": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0}])
    assigned = pd.DataFrame([{"Player": "A"}])
    sentinel = object()
    with patch.object(common_math, "common_replacement_pitcher_rates", return_value=sentinel) as mocked:
        result = dynasty_roto_values.common_replacement_pitcher_rates(all_pit, assigned, n_rep=10)
    mocked.assert_called_once_with(all_pit, assigned, 10)
    assert result is sentinel


def test_wrapper_common_apply_pitching_bounds_delegates() -> None:
    totals = {"IP": 1.0}
    lg = CommonDynastyRotoSettings()
    rates = {"W": 0.1}
    sentinel = object()
    with patch.object(common_math, "common_apply_pitching_bounds", return_value=sentinel) as mocked:
        result = dynasty_roto_values.common_apply_pitching_bounds(
            totals,
            lg,
            rates,
            fill_to_ip_max=False,
            enforce_ip_min=False,
        )
    mocked.assert_called_once_with(
        totals,
        lg,
        rates,
        fill_to_ip_max=False,
        enforce_ip_min=False,
    )
    assert result is sentinel


def test_wrapper_coerce_non_negative_float_delegates() -> None:
    sentinel = object()
    with patch.object(common_math, "_coerce_non_negative_float", return_value=sentinel) as mocked:
        result = dynasty_roto_values._coerce_non_negative_float("1")
    mocked.assert_called_once_with("1")
    assert result is sentinel


def test_wrapper_low_volume_positive_credit_scale_delegates() -> None:
    sentinel = object()
    with patch.object(common_math, "_low_volume_positive_credit_scale", return_value=sentinel) as mocked:
        result = dynasty_roto_values._low_volume_positive_credit_scale(
            pitcher_ip=10.0,
            slot_ip_reference=100.0,
            min_share_for_positive_ratio_credit=0.2,
            full_share_for_positive_ratio_credit=0.9,
        )
    mocked.assert_called_once_with(
        pitcher_ip=10.0,
        slot_ip_reference=100.0,
        min_share_for_positive_ratio_credit=0.2,
        full_share_for_positive_ratio_credit=0.9,
    )
    assert result is sentinel


def test_wrapper_apply_low_volume_non_ratio_positive_guard_delegates() -> None:
    delta = {"W": 1.0}
    sentinel = object()
    with patch.object(common_math, "_apply_low_volume_non_ratio_positive_guard", return_value=sentinel) as mocked:
        result = dynasty_roto_values._apply_low_volume_non_ratio_positive_guard(
            delta,
            pit_categories=["W"],
            pitcher_ip=10.0,
            slot_ip_reference=100.0,
            min_share_for_positive_ratio_credit=0.35,
            full_share_for_positive_ratio_credit=1.0,
        )
    mocked.assert_called_once_with(
        delta,
        pit_categories=["W"],
        pitcher_ip=10.0,
        slot_ip_reference=100.0,
        min_share_for_positive_ratio_credit=0.35,
        full_share_for_positive_ratio_credit=1.0,
    )
    assert result is sentinel


def test_wrapper_apply_low_volume_ratio_guard_delegates() -> None:
    delta = {"ERA": 1.0}
    sentinel = object()
    with patch.object(common_math, "_apply_low_volume_ratio_guard", return_value=sentinel) as mocked:
        result = dynasty_roto_values._apply_low_volume_ratio_guard(
            delta,
            pit_categories=["ERA"],
            pitcher_ip=10.0,
            slot_ip_reference=100.0,
            min_share_for_positive_ratio_credit=0.35,
            full_share_for_positive_ratio_credit=1.0,
        )
    mocked.assert_called_once_with(
        delta,
        pit_categories=["ERA"],
        pitcher_ip=10.0,
        slot_ip_reference=100.0,
        min_share_for_positive_ratio_credit=0.35,
        full_share_for_positive_ratio_credit=1.0,
    )
    assert result is sentinel


def test_wrapper_mean_adjacent_rank_gap_delegates() -> None:
    values = np.array([1.0, 2.0, 3.0])
    sentinel = object()
    with patch.object(common_math, "_mean_adjacent_rank_gap", return_value=sentinel) as mocked:
        result = dynasty_roto_values._mean_adjacent_rank_gap(values, ascending=False)
    mocked.assert_called_once_with(values, ascending=False)
    assert result is sentinel


def test_wrapper_simulate_sgp_hit_delegates() -> None:
    assigned = pd.DataFrame([{"AssignedSlot": "UT"}])
    lg = CommonDynastyRotoSettings(hitter_slots={"UT": 1}, pitcher_slots={"P": 1})
    rng = np.random.default_rng(11)
    sentinel = object()
    with patch.object(common_math, "simulate_sgp_hit", return_value=sentinel) as mocked:
        result = dynasty_roto_values.simulate_sgp_hit(assigned, lg, rng, categories=["R"]) 
    mocked.assert_called_once_with(assigned, lg, rng, categories=["R"])
    assert result is sentinel


def test_wrapper_simulate_sgp_pit_delegates() -> None:
    assigned = pd.DataFrame([{"AssignedSlot": "P"}])
    lg = CommonDynastyRotoSettings(hitter_slots={"UT": 1}, pitcher_slots={"P": 1})
    rng = np.random.default_rng(12)
    rates = {"W": 0.1}
    sentinel = object()
    with patch.object(common_math, "simulate_sgp_pit", return_value=sentinel) as mocked:
        result = dynasty_roto_values.simulate_sgp_pit(assigned, lg, rng, rep_rates=rates, categories=["W"])
    mocked.assert_called_once_with(assigned, lg, rng, rep_rates=rates, categories=["W"])
    assert result is sentinel


def test_wrapper_compute_year_context_delegates() -> None:
    bat = pd.DataFrame([{"Year": 2026}])
    pit = pd.DataFrame([{"Year": 2026}])
    lg = CommonDynastyRotoSettings()
    sentinel = object()
    with patch.object(common_math, "compute_year_context", return_value=sentinel) as mocked:
        result = dynasty_roto_values.compute_year_context(2026, bat, pit, lg, rng_seed=9)
    mocked.assert_called_once_with(2026, bat, pit, lg, rng_seed=9)
    assert result is sentinel


def test_wrapper_compute_year_player_values_delegates() -> None:
    ctx = {"year": 2026}
    lg = CommonDynastyRotoSettings()
    sentinel = object()
    with patch.object(common_math, "compute_year_player_values", return_value=sentinel) as mocked:
        result = dynasty_roto_values.compute_year_player_values(ctx, lg)
    mocked.assert_called_once_with(ctx, lg)
    assert result is sentinel


def test_wrapper_compute_replacement_baselines_delegates() -> None:
    ctx = {"year": 2026}
    lg = CommonDynastyRotoSettings()
    sentinel = object()
    with patch.object(common_math, "compute_replacement_baselines", return_value=sentinel) as mocked:
        result = dynasty_roto_values.compute_replacement_baselines(ctx, lg, rostered_players={"A"}, n_repl=2)
    mocked.assert_called_once_with(ctx, lg, rostered_players={"A"}, n_repl=2)
    assert result is sentinel


def test_wrapper_compute_year_player_values_vs_replacement_delegates() -> None:
    ctx = {"year": 2026}
    lg = CommonDynastyRotoSettings()
    repl_hit = pd.DataFrame([{"AssignedSlot": "UT"}]).set_index("AssignedSlot")
    repl_pit = pd.DataFrame([{"AssignedSlot": "P"}]).set_index("AssignedSlot")
    sentinel = object()
    with patch.object(common_math, "compute_year_player_values_vs_replacement", return_value=sentinel) as mocked:
        result = dynasty_roto_values.compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)
    mocked.assert_called_once_with(ctx, lg, repl_hit=repl_hit, repl_pit=repl_pit)
    assert result is sentinel


def test_wrapper_combine_two_way_delegates() -> None:
    hit_vals = pd.DataFrame([{"Player": "A", "Year": 2026, "YearValue": 1.0, "BestSlot": "UT", "Team": "AAA", "Age": 25, "Pos": "1B"}])
    pit_vals = pd.DataFrame([{"Player": "A", "Year": 2026, "YearValue": 2.0, "BestSlot": "P", "Team": "AAA", "Age": 25, "Pos": "SP"}])
    sentinel = object()
    with patch.object(common_math, "combine_two_way", return_value=sentinel) as mocked:
        result = dynasty_roto_values.combine_two_way(hit_vals, pit_vals, "max")
    mocked.assert_called_once_with(hit_vals, pit_vals, "max")
    assert result is sentinel
