from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend.valuation import common_math
from backend.valuation.models import PIT_COMPONENT_COLS, CommonDynastyRotoSettings


def _sample_common_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    bat = pd.DataFrame(
        [
            {
                "Player": "Hitter One",
                "Year": 2026,
                "Team": "AAA",
                "Age": 27,
                "Pos": "1B",
                "AB": 540.0,
                "H": 155.0,
                "R": 88.0,
                "HR": 28.0,
                "RBI": 94.0,
                "SB": 7.0,
                "BB": 62.0,
                "HBP": 4.0,
                "SF": 5.0,
                "2B": 32.0,
                "3B": 2.0,
            }
        ]
    )
    pit = pd.DataFrame(
        [
            {
                "Player": "Pitcher One",
                "Year": 2026,
                "Team": "AAA",
                "Age": 29,
                "Pos": "SP",
                "IP": 170.0,
                "W": 12.0,
                "QS": 18.0,
                "QA3": 20.0,
                "K": 185.0,
                "SV": 0.0,
                "SVH": 0.0,
                "ER": 64.0,
                "H": 152.0,
                "BB": 50.0,
                "ERA": 3.39,
                "WHIP": 1.19,
            }
        ]
    )
    return bat, pit


def test_common_apply_pitching_bounds_scales_over_cap_and_fills_under_cap() -> None:
    lg = CommonDynastyRotoSettings(ip_min=0.0, ip_max=100.0)

    over_totals = {col: 0.0 for col in PIT_COMPONENT_COLS}
    over_totals.update({"IP": 200.0, "W": 20.0, "K": 200.0, "SV": 10.0, "SVH": 15.0, "QS": 25.0, "QA3": 30.0, "ER": 80.0, "H": 160.0, "BB": 60.0})
    over = common_math.common_apply_pitching_bounds(over_totals, lg, rep_rates=None)

    assert over["IP"] == 100.0
    assert over["W"] == 10.0
    assert math.isclose(over["ERA"], 9.0 * 40.0 / 100.0)

    under_totals = {col: 0.0 for col in PIT_COMPONENT_COLS}
    under_totals.update({"IP": 80.0, "W": 8.0, "K": 80.0, "SV": 4.0, "SVH": 8.0, "QS": 10.0, "QA3": 12.0, "ER": 32.0, "H": 64.0, "BB": 24.0})
    rates = {"W": 0.1, "QS": 0.1, "QA3": 0.1, "K": 1.0, "SV": 0.05, "SVH": 0.1, "ER": 0.4, "H": 0.8, "BB": 0.3}
    under = common_math.common_apply_pitching_bounds(under_totals, lg, rep_rates=rates)

    assert under["IP"] == 100.0
    assert under["W"] == 10.0
    assert under["K"] == 100.0


def test_common_apply_pitching_bounds_enforces_ip_min_when_requested() -> None:
    lg = CommonDynastyRotoSettings(ip_min=100.0, ip_max=None)
    totals = {col: 0.0 for col in PIT_COMPONENT_COLS}
    totals.update({"IP": 80.0, "ER": 24.0, "H": 70.0, "BB": 30.0})

    bounded = common_math.common_apply_pitching_bounds(totals, lg, rep_rates=None, enforce_ip_min=True)
    not_enforced = common_math.common_apply_pitching_bounds(totals, lg, rep_rates=None, enforce_ip_min=False)

    assert bounded["ERA"] == 99.0
    assert bounded["WHIP"] == 5.0
    assert not_enforced["ERA"] != 99.0
    assert not_enforced["WHIP"] != 5.0


def test_simulate_sgp_hit_and_pit_return_expected_categories() -> None:
    lg = CommonDynastyRotoSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"UT": 1},
        pitcher_slots={"P": 1},
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
        ip_min=0.0,
        ip_max=150.0,
    )

    assigned_hit = pd.DataFrame(
        [
            {
                "AssignedSlot": "UT",
                "AB": 500.0,
                "H": 145.0,
                "R": 80.0,
                "HR": 25.0,
                "RBI": 90.0,
                "SB": 8.0,
                "BB": 60.0,
                "HBP": 3.0,
                "SF": 4.0,
                "2B": 30.0,
                "3B": 2.0,
            }
        ]
    )
    assigned_pit = pd.DataFrame(
        [
            {
                "AssignedSlot": "P",
                "IP": 160.0,
                "W": 12.0,
                "QS": 18.0,
                "QA3": 19.0,
                "K": 180.0,
                "SV": 0.0,
                "SVH": 0.0,
                "ER": 60.0,
                "H": 150.0,
                "BB": 45.0,
            }
        ]
    )

    sgp_hit = common_math.simulate_sgp_hit(assigned_hit, lg, np.random.default_rng(3))
    sgp_pit = common_math.simulate_sgp_pit(
        assigned_pit,
        lg,
        np.random.default_rng(4),
        rep_rates={"W": 0.0, "QS": 0.0, "QA3": 0.0, "K": 0.0, "SV": 0.0, "SVH": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0},
    )

    assert set(sgp_hit.keys()) == set(lg.hitter_categories)
    assert set(sgp_pit.keys()) == set(lg.pitcher_categories)
    assert all(np.isfinite(float(v)) for v in sgp_hit.values())
    assert all(np.isfinite(float(v)) for v in sgp_pit.values())


def test_simulate_sgp_robust_mode_applies_denominator_floors() -> None:
    lg = CommonDynastyRotoSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"UT": 1},
        pitcher_slots={"P": 1},
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
        ip_min=0.0,
        ip_max=150.0,
        sgp_denominator_mode="robust",
        sgp_epsilon_counting=0.2,
        sgp_epsilon_ratio=0.005,
    )

    assigned_hit = pd.DataFrame(
        [
            {
                "AssignedSlot": "UT",
                "AB": 500.0,
                "H": 145.0,
                "R": 80.0,
                "HR": 25.0,
                "RBI": 90.0,
                "SB": 8.0,
                "BB": 60.0,
                "HBP": 3.0,
                "SF": 4.0,
                "2B": 30.0,
                "3B": 2.0,
            }
        ]
    )
    assigned_pit = pd.DataFrame(
        [
            {
                "AssignedSlot": "P",
                "IP": 160.0,
                "W": 12.0,
                "QS": 18.0,
                "QA3": 19.0,
                "K": 180.0,
                "SV": 0.0,
                "SVH": 0.0,
                "ER": 60.0,
                "H": 150.0,
                "BB": 45.0,
            }
        ]
    )

    sgp_hit = common_math.simulate_sgp_hit(
        assigned_hit,
        lg,
        np.random.default_rng(3),
        categories=["R", "AVG"],
    )
    sgp_pit = common_math.simulate_sgp_pit(
        assigned_pit,
        lg,
        np.random.default_rng(4),
        rep_rates={"W": 0.0, "QS": 0.0, "QA3": 0.0, "K": 0.0, "SV": 0.0, "SVH": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0},
        categories=["W", "ERA"],
    )

    assert sgp_hit["R"] >= 0.2
    assert sgp_hit["AVG"] >= 0.005
    assert sgp_pit["W"] >= 0.2
    assert sgp_pit["ERA"] >= 0.005


def test_compute_year_context_and_values_smoke() -> None:
    bat, pit = _sample_common_frames()
    lg = CommonDynastyRotoSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"UT": 1},
        pitcher_slots={"P": 1},
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
        ip_min=0.0,
        ip_max=180.0,
    )

    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=5)
    assert {"baseline_hit", "baseline_pit", "sgp_hit", "sgp_pit", "rep_rates"}.issubset(ctx.keys())

    hit_vals, pit_vals = common_math.compute_year_player_values(ctx, lg)
    assert len(hit_vals) == 1
    assert len(pit_vals) == 1
    assert np.isfinite(float(hit_vals["YearValue"].iloc[0]))
    assert np.isfinite(float(pit_vals["YearValue"].iloc[0]))


def test_compute_year_context_raises_clear_error_for_empty_playing_time() -> None:
    bat = pd.DataFrame([{"Player": "NoAB", "Year": 2026, "Team": "AAA", "Age": 23, "Pos": "UT", "AB": 0.0}])
    pit = pd.DataFrame([{"Player": "Pitch", "Year": 2026, "Team": "AAA", "Age": 29, "Pos": "P", "IP": 10.0}])
    lg = CommonDynastyRotoSettings(n_teams=1, hitter_slots={"UT": 1}, pitcher_slots={"P": 1})

    try:
        common_math.compute_year_context(2026, bat, pit, lg, rng_seed=1)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "no hitters with AB > 0" in str(exc)


def test_low_volume_guards_scale_positive_components_only() -> None:
    delta = {"W": 2.0, "ERA": 1.5, "WHIP": 1.0}

    common_math._apply_low_volume_non_ratio_positive_guard(
        delta,
        pit_categories=["W", "ERA", "WHIP"],
        pitcher_ip=10.0,
        slot_ip_reference=100.0,
    )
    assert delta["W"] == 0.0
    assert delta["ERA"] == 1.5

    common_math._apply_low_volume_ratio_guard(
        delta,
        pit_categories=["W", "ERA", "WHIP"],
        pitcher_ip=10.0,
        slot_ip_reference=100.0,
    )
    assert delta["ERA"] == 0.0
    assert delta["WHIP"] == 0.0


def test_playing_time_reliability_helpers_scale_positive_components_only() -> None:
    hit_delta = {"R": 2.0, "AVG": 0.01, "SB": -0.2}
    common_math._apply_hitter_playing_time_reliability_guard(
        hit_delta,
        hit_categories=["R", "AVG", "SB"],
        hitter_ab=40.0,
        slot_ab_reference=200.0,
    )
    assert hit_delta["R"] == 0.0
    assert hit_delta["AVG"] == 0.0
    assert hit_delta["SB"] == -0.2

    pit_delta = {"W": 1.2, "ERA": 0.8, "WHIP": -0.1}
    common_math._apply_pitcher_playing_time_reliability_guard(
        pit_delta,
        pit_categories=["W", "ERA", "WHIP"],
        pitcher_ip=20.0,
        slot_ip_reference=100.0,
    )
    assert pit_delta["W"] == 0.0
    assert pit_delta["ERA"] == 0.0
    assert pit_delta["WHIP"] == -0.1


def test_replacement_and_vs_replacement_paths_smoke() -> None:
    bat, pit = _sample_common_frames()
    lg = CommonDynastyRotoSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"UT": 1},
        pitcher_slots={"P": 1},
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
        ip_min=0.0,
        ip_max=180.0,
    )

    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=7)
    repl_hit, repl_pit = common_math.compute_replacement_baselines(ctx, lg, rostered_players={"Nobody"}, n_repl=1)

    assert not repl_hit.empty
    assert not repl_pit.empty

    hit_vals, pit_vals = common_math.compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)
    assert len(hit_vals) == 1
    assert len(pit_vals) == 1


def test_zscore_returns_zeros_when_all_equal() -> None:
    s = pd.Series([5.0, 5.0, 5.0])
    result = common_math._zscore(s)
    assert (result == 0.0).all()


def test_zscore_returns_zeros_for_single_value() -> None:
    s = pd.Series([3.14])
    result = common_math._zscore(s)
    assert (result == 0.0).all()


def test_zscore_normal_case() -> None:
    s = pd.Series([1.0, 2.0, 3.0])
    result = common_math._zscore(s)
    assert result.iloc[0] < 0  # Below mean
    assert abs(result.iloc[1]) < 1e-10  # At mean
    assert result.iloc[2] > 0  # Above mean


def test_positive_credit_scale_zero_slot_volume() -> None:
    scale = common_math._positive_credit_scale(
        player_volume=50.0,
        slot_volume_reference=0.0,
    )
    assert scale == 1.0


def test_positive_credit_scale_full_credit() -> None:
    scale = common_math._positive_credit_scale(
        player_volume=200.0,
        slot_volume_reference=200.0,
    )
    assert scale == 1.0


def test_positive_credit_scale_below_min_share() -> None:
    scale = common_math._positive_credit_scale(
        player_volume=10.0,
        slot_volume_reference=200.0,
        min_share_for_positive_credit=0.35,
    )
    assert scale == 0.0


def test_positive_credit_scale_linear_interpolation() -> None:
    # 50% share, min=0.35, full=1.0 → linear between 0 and 1
    scale = common_math._positive_credit_scale(
        player_volume=100.0,
        slot_volume_reference=200.0,
        min_share_for_positive_credit=0.35,
        full_share_for_positive_credit=1.00,
    )
    assert 0.0 < scale < 1.0
    expected = (0.5 - 0.35) / (1.0 - 0.35)
    assert math.isclose(scale, expected, rel_tol=1e-6)


def test_positive_credit_scale_inverted_min_full() -> None:
    # When full_share <= min_share, binary behavior
    scale = common_math._positive_credit_scale(
        player_volume=60.0,
        slot_volume_reference=100.0,
        min_share_for_positive_credit=0.80,
        full_share_for_positive_credit=0.50,
    )
    assert scale == 1.0  # share=0.6 >= full_share=0.5


def test_mean_adjacent_rank_gap_basic() -> None:
    values = np.array([1.0, 3.0, 6.0, 10.0])
    gap = common_math._mean_adjacent_rank_gap(values, ascending=True)
    # Sorted ascending: [1, 3, 6, 10] → diffs = [2, 3, 4] → mean = 3.0
    assert math.isclose(gap, 3.0)


def test_mean_adjacent_rank_gap_descending() -> None:
    values = np.array([1.0, 3.0, 6.0, 10.0])
    gap = common_math._mean_adjacent_rank_gap(values, ascending=False)
    # Sorted descending: [10, 6, 3, 1] → diffs = [4, 3, 2] → mean = 3.0
    assert math.isclose(gap, 3.0)


def test_mean_adjacent_rank_gap_single_value() -> None:
    assert common_math._mean_adjacent_rank_gap(np.array([5.0]), ascending=True) == 0.0


def test_mean_adjacent_rank_gap_with_nan_inf() -> None:
    values = np.array([1.0, float("nan"), 3.0, float("inf"), 5.0])
    gap = common_math._mean_adjacent_rank_gap(values, ascending=True)
    # After filtering: [1, 3, 5] → diffs = [2, 2] → mean = 2.0
    assert math.isclose(gap, 2.0)


def test_mean_adjacent_rank_gap_robust_winsorizing() -> None:
    values = np.array([1.0, 2.0, 3.0, 4.0, 100.0])
    gap_classic = common_math._mean_adjacent_rank_gap(values, ascending=True, robust=False)
    gap_robust = common_math._mean_adjacent_rank_gap(
        values, ascending=True, robust=True, winsor_low_pct=0.1, winsor_high_pct=0.9,
    )
    # Robust clips outlier diffs, so gap_robust <= gap_classic
    assert gap_robust <= gap_classic


def test_common_hit_category_totals_basic() -> None:
    totals = {
        "AB": 500.0, "H": 150.0, "R": 80.0, "HR": 25.0, "RBI": 90.0,
        "SB": 10.0, "BB": 60.0, "HBP": 3.0, "SF": 4.0, "2B": 30.0, "3B": 2.0,
    }
    result = common_math.common_hit_category_totals(totals)
    assert math.isclose(result["AVG"], 150 / 500)
    # OBP = (H + BB + HBP) / (AB + BB + HBP + SF)
    assert math.isclose(result["OBP"], (150 + 60 + 3) / (500 + 60 + 3 + 4))
    # TB = H + 2B + 2*3B + 3*HR
    expected_tb = 150 + 30 + 2 * 2 + 3 * 25
    assert math.isclose(result["TB"], expected_tb)


def test_common_replacement_pitcher_rates_empty_pool() -> None:
    assigned_pit = pd.DataFrame([
        {"Player": "P1", "IP": 150.0, "W": 10.0, "K": 150.0, "SV": 0.0, "SVH": 0.0,
         "QS": 15.0, "QA3": 18.0, "ER": 50.0, "H": 130.0, "BB": 40.0,
         "ERA": 3.0, "WHIP": 1.13, "AssignedSlot": "P", "weight": 5.0}
    ])
    all_pit = assigned_pit.copy()  # Only the rostered pitcher exists
    rates = common_math.common_replacement_pitcher_rates(all_pit, assigned_pit, n_rep=5)
    # All rates should be 0 since there are no free agents
    assert all(v == 0.0 for v in rates.values())


def test_combine_two_way_supports_max_and_sum() -> None:
    hit_vals = pd.DataFrame(
        [
            {"Player": "TwoWay", "Year": 2026, "YearValue": 5.0, "BestSlot": "UT", "Team": "AAA", "Age": 25, "Pos": "1B"},
            {"Player": "OnlyHit", "Year": 2026, "YearValue": 3.0, "BestSlot": "UT", "Team": "BBB", "Age": 27, "Pos": "OF"},
        ]
    )
    pit_vals = pd.DataFrame(
        [
            {"Player": "TwoWay", "Year": 2026, "YearValue": 6.0, "BestSlot": "P", "Team": "AAA", "Age": 25, "Pos": "SP"},
            {"Player": "OnlyPit", "Year": 2026, "YearValue": 4.0, "BestSlot": "P", "Team": "CCC", "Age": 29, "Pos": "RP"},
        ]
    )

    max_mode = common_math.combine_two_way(hit_vals, pit_vals, two_way="max")
    sum_mode = common_math.combine_two_way(hit_vals, pit_vals, two_way="sum")

    max_by_player = {row.Player: (float(row.YearValue), row.BestSlot) for row in max_mode.itertuples(index=False)}
    sum_by_player = {row.Player: (float(row.YearValue), row.BestSlot) for row in sum_mode.itertuples(index=False)}

    assert max_by_player["TwoWay"] == (6.0, "P")
    assert sum_by_player["TwoWay"] == (11.0, "UT+P")
    assert max_by_player["OnlyHit"] == (3.0, "UT")
    assert max_by_player["OnlyPit"] == (4.0, "P")
