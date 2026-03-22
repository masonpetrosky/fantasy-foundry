from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from backend.valuation import common_math
from backend.valuation import replacement as replacement_math
from backend.valuation.models import HIT_COMPONENT_COLS, PIT_COMPONENT_COLS, CommonDynastyRotoSettings

pytestmark = pytest.mark.valuation


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


def test_common_apply_pitching_bounds_scales_over_cap_without_filling_under_cap() -> None:
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

    assert under["IP"] == 80.0
    assert under["W"] == 8.0
    assert under["K"] == 80.0


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


def test_common_apply_pitching_bounds_can_fill_to_ip_min_with_replacement_rates() -> None:
    lg = CommonDynastyRotoSettings(ip_min=100.0, ip_max=None)
    totals = {col: 0.0 for col in PIT_COMPONENT_COLS}
    totals.update({"IP": 80.0, "W": 8.0, "K": 80.0, "ER": 24.0, "H": 70.0, "BB": 30.0, "QA3": 10.0, "SVH": 4.0})
    rep_rates = {
        "W": 0.1,
        "QS": 0.05,
        "QA3": 0.08,
        "K": 1.0,
        "SV": 0.02,
        "SVH": 0.07,
        "ER": 0.4,
        "H": 0.8,
        "BB": 0.3,
    }

    filled = common_math.common_apply_pitching_bounds(
        totals,
        lg,
        rep_rates=rep_rates,
        fill_to_ip_min=True,
        enforce_ip_min=True,
    )
    unfilled = common_math.common_apply_pitching_bounds(
        totals,
        lg,
        rep_rates=rep_rates,
        fill_to_ip_min=False,
        enforce_ip_min=True,
    )

    assert filled["IP"] == 100.0
    assert math.isclose(filled["W"], 10.0)
    assert math.isclose(filled["K"], 100.0)
    assert math.isclose(filled["QA3"], 11.6)
    assert math.isclose(filled["SVH"], 5.4)
    assert math.isclose(filled["ERA"], 2.88)
    assert math.isclose(filled["WHIP"], 1.22)
    assert unfilled["ERA"] == 99.0
    assert unfilled["WHIP"] == 5.0


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
    assert ctx["bat_y"] is ctx.bat_y
    assert ctx.get("assigned_hit") is ctx.assigned_hit

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


def test_compute_replacement_baselines_falls_back_when_unrostered_pool_is_empty() -> None:
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

    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=11)
    repl_hit, repl_pit = common_math.compute_replacement_baselines(
        ctx,
        lg,
        rostered_players={"Hitter One", "Pitcher One"},
        n_repl=1,
    )

    assert list(repl_hit.index) == ["UT"]
    assert list(repl_pit.index) == ["P"]
    assert math.isclose(float(repl_hit.loc["UT", "AB"]), float(ctx["baseline_hit"].loc["UT", "AB"]))
    assert math.isclose(float(repl_pit.loc["P", "IP"]), float(ctx["baseline_pit"].loc["P", "IP"]))


def test_compute_replacement_baselines_can_use_depth_aware_of_and_p_pools() -> None:
    def _hit_row(player: str, pos: str, *, ab: float, r: float) -> dict[str, float | str]:
        row: dict[str, float | str] = {col: 0.0 for col in HIT_COMPONENT_COLS}
        row.update({"Player": player, "Pos": pos, "AB": ab, "H": ab * 0.28, "R": r})
        return row

    def _pit_row(player: str, pos: str, *, ip: float, w: float) -> dict[str, float | str]:
        row: dict[str, float | str] = {col: 0.0 for col in PIT_COMPONENT_COLS}
        row.update({"Player": player, "Pos": pos, "IP": ip, "W": w})
        return row

    ctx = {
        "bat_y": pd.DataFrame(
            [
                _hit_row(f"OF {idx}", "OF", ab=500.0 - idx, r=100.0 - idx * 5.0)
                for idx in range(8)
            ]
            + [
                _hit_row("C 1", "C", ab=430.0, r=55.0),
                _hit_row("C 2", "C", ab=410.0, r=45.0),
            ]
        ),
        "pit_y": pd.DataFrame(
            [
                _pit_row(f"P {idx}", "SP", ip=175.0 - idx * 3.0, w=14.0 - idx)
                for idx in range(7)
            ]
        ),
        "baseline_hit": pd.DataFrame(
            [
                {"AssignedSlot": "OF", **{col: 0.0 for col in HIT_COMPONENT_COLS}},
                {"AssignedSlot": "C", **{col: 0.0 for col in HIT_COMPONENT_COLS}},
            ]
        ).set_index("AssignedSlot"),
        "baseline_pit": pd.DataFrame(
            [
                {"AssignedSlot": "P", **{col: 0.0 for col in PIT_COMPONENT_COLS}},
            ]
        ).set_index("AssignedSlot"),
        "hit_categories": ["R"],
        "pit_categories": ["W"],
    }

    flat_lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5, "C": 1},
        pitcher_slots={"P": 4},
        replacement_depth_mode="flat",
    )
    full_lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5, "C": 1},
        pitcher_slots={"P": 4},
        replacement_depth_mode="full_depth",
    )

    flat_hit, flat_pit = common_math.compute_replacement_baselines(ctx, flat_lg, rostered_players=set(), n_repl=2)
    full_hit, full_pit = common_math.compute_replacement_baselines(ctx, full_lg, rostered_players=set(), n_repl=2)

    assert int(flat_hit.loc["OF", "ReplacementPoolDepth"]) == 2
    assert int(full_hit.loc["OF", "ReplacementPoolDepth"]) == 8
    assert str(full_hit.loc["OF", "ReplacementDepthMode"]) == "full_depth"
    assert int(full_hit.loc["OF", "SlotCountPerTeam"]) == 5
    assert int(full_hit.loc["OF", "SlotCapacityLeague"]) == 10
    assert float(full_hit.loc["OF", "R"]) < float(flat_hit.loc["OF", "R"])

    assert int(flat_pit.loc["P", "ReplacementPoolDepth"]) == 2
    assert int(full_pit.loc["P", "ReplacementPoolDepth"]) == 7
    assert str(full_pit.loc["P", "ReplacementDepthMode"]) == "full_depth"
    assert int(full_pit.loc["P", "SlotCountPerTeam"]) == 4
    assert int(full_pit.loc["P", "SlotCapacityLeague"]) == 8
    assert float(full_pit.loc["P", "W"]) < float(flat_pit.loc["P", "W"])

    assert int(full_hit.loc["C", "ReplacementPoolDepth"]) == 2
    assert str(full_hit.loc["C", "ReplacementDepthMode"]) == "flat"


def test_compute_replacement_baselines_blended_depth_uses_internal_alpha() -> None:
    def _hit_row(player: str, pos: str, *, ab: float, r: float) -> dict[str, float | str]:
        row: dict[str, float | str] = {col: 0.0 for col in HIT_COMPONENT_COLS}
        row.update({"Player": player, "Pos": pos, "AB": ab, "H": ab * 0.28, "R": r})
        return row

    ctx = {
        "bat_y": pd.DataFrame(
            [_hit_row(f"OF {idx}", "OF", ab=500.0 - idx * 10.0, r=100.0 - idx * 10.0) for idx in range(10)]
        ),
        "pit_y": pd.DataFrame(
            [
                {
                    "Player": "Dummy Pitcher",
                    "Pos": "SP",
                    **{col: 0.0 for col in PIT_COMPONENT_COLS},
                }
            ]
        ),
        "baseline_hit": pd.DataFrame(
            [{"AssignedSlot": "OF", **{col: 0.0 for col in HIT_COMPONENT_COLS}}]
        ).set_index("AssignedSlot"),
        "baseline_pit": pd.DataFrame(
            [{"AssignedSlot": "P", **{col: 0.0 for col in PIT_COMPONENT_COLS}}]
        ).set_index("AssignedSlot"),
        "hit_categories": ["R"],
        "pit_categories": ["W"],
    }

    flat_lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5},
        pitcher_slots={"P": 1},
        replacement_depth_mode="flat",
    )
    blended_lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5},
        pitcher_slots={"P": 1},
        replacement_depth_mode="blended_depth",
        replacement_depth_blend_alpha=0.25,
    )
    full_lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5},
        pitcher_slots={"P": 1},
        replacement_depth_mode="full_depth",
    )

    flat_hit, _ = common_math.compute_replacement_baselines(ctx, flat_lg, rostered_players=set(), n_repl=2)
    blended_hit, _ = common_math.compute_replacement_baselines(ctx, blended_lg, rostered_players=set(), n_repl=2)
    full_hit, _ = common_math.compute_replacement_baselines(ctx, full_lg, rostered_players=set(), n_repl=2)

    assert str(blended_hit.loc["OF", "ReplacementDepthMode"]) == "blended_depth"
    assert math.isclose(float(blended_hit.loc["OF", "ReplacementDepthBlendAlpha"]), 0.25)
    assert int(blended_hit.loc["OF", "ReplacementPoolDepth"]) == 4
    assert float(flat_hit.loc["OF", "R"]) > float(blended_hit.loc["OF", "R"]) > float(full_hit.loc["OF", "R"])


def _depth_aware_replacement_context() -> dict[str, pd.DataFrame | list[str]]:
    def _hit_row(player: str, pos: str, *, ab: float, r: float) -> dict[str, float | str]:
        row: dict[str, float | str] = {col: 0.0 for col in HIT_COMPONENT_COLS}
        row.update({"Player": player, "Pos": pos, "AB": ab, "H": ab * 0.28, "R": r})
        return row

    def _pit_row(player: str, pos: str, *, ip: float, k: float) -> dict[str, float | str]:
        row: dict[str, float | str] = {col: 0.0 for col in PIT_COMPONENT_COLS}
        row.update({"Player": player, "Pos": pos, "IP": ip, "K": k})
        return row

    return {
        "bat_y": pd.DataFrame(
            [_hit_row(f"OF {idx}", "OF", ab=500.0 - idx * 10.0, r=100.0 - idx * 10.0) for idx in range(10)]
        ),
        "pit_y": pd.DataFrame(
            [_pit_row(f"SP {idx}", "SP", ip=180.0 - idx * 5.0, k=210.0 - idx * 8.0) for idx in range(10)]
        ),
        "baseline_hit": pd.DataFrame(
            [{"AssignedSlot": "OF", **{col: 0.0 for col in HIT_COMPONENT_COLS}}]
        ).set_index("AssignedSlot"),
        "baseline_pit": pd.DataFrame(
            [{"AssignedSlot": "P", **{col: 0.0 for col in PIT_COMPONENT_COLS}}]
        ).set_index("AssignedSlot"),
        "hit_categories": ["R"],
        "pit_categories": ["K"],
    }


def test_compute_replacement_baselines_blended_depth_without_slot_override_preserves_shared_alpha() -> None:
    ctx = _depth_aware_replacement_context()
    lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5},
        pitcher_slots={"P": 4},
        replacement_depth_mode="blended_depth",
        replacement_depth_blend_alpha=0.33,
    )

    repl_hit, repl_pit = common_math.compute_replacement_baselines(ctx, lg, rostered_players=set(), n_repl=2)

    assert math.isclose(float(repl_hit.loc["OF", "ReplacementDepthBlendAlpha"]), 0.33)
    assert math.isclose(float(repl_pit.loc["P", "ReplacementDepthBlendAlpha"]), 0.33)


def test_compute_replacement_baselines_blended_depth_of_override_changes_only_of() -> None:
    ctx = _depth_aware_replacement_context()
    lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5},
        pitcher_slots={"P": 4},
        replacement_depth_mode="blended_depth",
        replacement_depth_blend_alpha=0.33,
        replacement_depth_blend_alpha_by_slot={"OF": 0.20},
    )

    repl_hit, repl_pit = common_math.compute_replacement_baselines(ctx, lg, rostered_players=set(), n_repl=2)

    assert math.isclose(float(repl_hit.loc["OF", "ReplacementDepthBlendAlpha"]), 0.20)
    assert math.isclose(float(repl_pit.loc["P", "ReplacementDepthBlendAlpha"]), 0.33)


def test_compute_replacement_baselines_blended_depth_p_override_changes_only_generic_p() -> None:
    ctx = _depth_aware_replacement_context()
    lg = CommonDynastyRotoSettings(
        n_teams=2,
        hitter_slots={"OF": 5},
        pitcher_slots={"P": 4},
        replacement_depth_mode="blended_depth",
        replacement_depth_blend_alpha=0.33,
        replacement_depth_blend_alpha_by_slot={"P": 0.25},
    )

    repl_hit, repl_pit = common_math.compute_replacement_baselines(ctx, lg, rostered_players=set(), n_repl=2)

    assert math.isclose(float(repl_hit.loc["OF", "ReplacementDepthBlendAlpha"]), 0.33)
    assert math.isclose(float(repl_pit.loc["P", "ReplacementDepthBlendAlpha"]), 0.25)


def test_compute_year_player_values_applies_hitter_reliability_guard_once(monkeypatch) -> None:
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
        enable_playing_time_reliability=True,
    )
    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=13)
    calls: list[float] = []

    def fake_guard(delta, *, hit_categories, hitter_ab, slot_ab_reference) -> None:
        calls.append(float(hitter_ab))

    monkeypatch.setattr(common_math, "_apply_hitter_playing_time_reliability_guard", fake_guard)
    common_math.compute_year_player_values(ctx, lg)

    assert calls == [540.0]


def test_vs_replacement_path_applies_hitter_reliability_guard_once(monkeypatch) -> None:
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
        enable_playing_time_reliability=True,
    )
    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=17)
    repl_hit, repl_pit = common_math.compute_replacement_baselines(ctx, lg, rostered_players={"Nobody"}, n_repl=1)
    calls: list[float] = []

    def fake_guard(delta, *, hit_categories, hitter_ab, slot_ab_reference) -> None:
        calls.append(float(hitter_ab))

    monkeypatch.setattr(replacement_math, "_apply_hitter_playing_time_reliability_guard", fake_guard)
    replacement_math.compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)

    assert calls == [540.0]


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


def test_compute_year_player_values_returns_sgp_columns() -> None:
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
    hit_vals, pit_vals = common_math.compute_year_player_values(ctx, lg)

    hit_sgp_cols = [c for c in hit_vals.columns if c.startswith("SGP_")]
    pit_sgp_cols = [c for c in pit_vals.columns if c.startswith("SGP_")]

    assert len(hit_sgp_cols) == len(lg.hitter_categories)
    assert len(pit_sgp_cols) == len(lg.pitcher_categories)

    for _, row in hit_vals.iterrows():
        sgp_sum = sum(float(row[c]) for c in hit_sgp_cols)
        assert math.isclose(sgp_sum, float(row["YearValue"]), abs_tol=1e-10)

    for _, row in pit_vals.iterrows():
        sgp_sum = sum(float(row[c]) for c in pit_sgp_cols)
        assert math.isclose(sgp_sum, float(row["YearValue"]), abs_tol=1e-10)


def test_compute_year_player_values_vs_replacement_returns_sgp_columns() -> None:
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
    hit_vals, pit_vals = common_math.compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)

    hit_sgp_cols = [c for c in hit_vals.columns if c.startswith("SGP_")]
    pit_sgp_cols = [c for c in pit_vals.columns if c.startswith("SGP_")]

    assert len(hit_sgp_cols) == len(lg.hitter_categories)
    assert len(pit_sgp_cols) == len(lg.pitcher_categories)

    for _, row in hit_vals.iterrows():
        sgp_sum = sum(float(row[c]) for c in hit_sgp_cols)
        assert math.isclose(sgp_sum, float(row["YearValue"]), abs_tol=1e-10)

    for _, row in pit_vals.iterrows():
        sgp_sum = sum(float(row[c]) for c in pit_sgp_cols)
        assert math.isclose(sgp_sum, float(row["YearValue"]), abs_tol=1e-10)


def test_compute_year_player_values_vs_replacement_includes_replacement_diagnostics() -> None:
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
    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=11)
    repl_hit, repl_pit = common_math.compute_replacement_baselines(ctx, lg, rostered_players={"Nobody"}, n_repl=1)
    hit_vals, pit_vals = common_math.compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)

    hit_diag = hit_vals.iloc[0]["ReplacementDiagnostics"]
    assert hit_diag["side"] == "hit"
    assert isinstance(hit_diag["best_slot"], str)
    assert isinstance(hit_diag["category_sgp"], dict)
    assert "slot_baseline_reference" in hit_diag
    assert "replacement_reference" in hit_diag
    assert "guard" in hit_diag

    pit_diag = pit_vals.iloc[0]["ReplacementDiagnostics"]
    assert pit_diag["side"] == "pit"
    assert isinstance(pit_diag["best_slot"], str)
    assert isinstance(pit_diag["category_sgp"], dict)
    assert "bounds" in pit_diag
    assert "player_raw_totals" in pit_diag["bounds"]


def test_combine_two_way_preserves_sgp_columns() -> None:
    hit_vals = pd.DataFrame([
        {"Player": "TwoWay", "Year": 2026, "YearValue": 5.0, "BestSlot": "UT", "Team": "AAA", "Age": 25, "Pos": "1B", "SGP_R": 2.0, "SGP_HR": 3.0},
        {"Player": "OnlyHit", "Year": 2026, "YearValue": 3.0, "BestSlot": "UT", "Team": "BBB", "Age": 27, "Pos": "OF", "SGP_R": 1.5, "SGP_HR": 1.5},
    ])
    pit_vals = pd.DataFrame([
        {"Player": "TwoWay", "Year": 2026, "YearValue": 6.0, "BestSlot": "P", "Team": "AAA", "Age": 25, "Pos": "SP", "SGP_W": 4.0, "SGP_ERA": 2.0},
        {"Player": "OnlyPit", "Year": 2026, "YearValue": 4.0, "BestSlot": "P", "Team": "CCC", "Age": 29, "Pos": "RP", "SGP_W": 2.5, "SGP_ERA": 1.5},
    ])

    sum_mode = common_math.combine_two_way(hit_vals, pit_vals, two_way="sum")
    sgp_cols = [c for c in sum_mode.columns if c.startswith("SGP_")]
    assert set(sgp_cols) == {"SGP_R", "SGP_HR", "SGP_W", "SGP_ERA"}

    tw = sum_mode[sum_mode["Player"] == "TwoWay"].iloc[0]
    assert math.isclose(float(tw["SGP_R"]), 2.0)
    assert math.isclose(float(tw["SGP_HR"]), 3.0)
    assert math.isclose(float(tw["SGP_W"]), 4.0)
    assert math.isclose(float(tw["SGP_ERA"]), 2.0)

    max_mode = common_math.combine_two_way(hit_vals, pit_vals, two_way="max")
    tw_max = max_mode[max_mode["Player"] == "TwoWay"].iloc[0]
    # max picks pit side (6 > 5), so only pit SGPs should be non-zero
    assert math.isclose(float(tw_max["SGP_W"]), 4.0)
    assert math.isclose(float(tw_max["SGP_ERA"]), 2.0)
    assert math.isclose(float(tw_max["SGP_R"]), 0.0)
    assert math.isclose(float(tw_max["SGP_HR"]), 0.0)

    # Hitter-only and pitcher-only players should have correct SGP values
    oh = max_mode[max_mode["Player"] == "OnlyHit"].iloc[0]
    assert math.isclose(float(oh["SGP_R"]), 1.5)
    op = max_mode[max_mode["Player"] == "OnlyPit"].iloc[0]
    assert math.isclose(float(op["SGP_W"]), 2.5)


def test_combine_two_way_preserves_replacement_diagnostics() -> None:
    hit_vals = pd.DataFrame([
        {
            "Player": "TwoWay",
            "Year": 2026,
            "YearValue": 5.0,
            "BestSlot": "UT",
            "Team": "AAA",
            "Age": 25,
            "Pos": "1B",
            "ReplacementDiagnostics": {"side": "hit", "best_slot": "UT", "category_sgp": {"R": 2.0}},
        },
    ])
    pit_vals = pd.DataFrame([
        {
            "Player": "TwoWay",
            "Year": 2026,
            "YearValue": 6.0,
            "BestSlot": "P",
            "Team": "AAA",
            "Age": 25,
            "Pos": "SP",
            "ReplacementDiagnostics": {"side": "pit", "best_slot": "P", "category_sgp": {"W": 4.0}},
        },
    ])

    sum_mode = common_math.combine_two_way(hit_vals, pit_vals, two_way="sum")
    sum_diag = sum_mode.iloc[0]["ReplacementDiagnostics"]
    assert sum_diag["two_way_mode"] == "sum"
    assert sum_diag["best_slot"] == "UT+P"
    assert math.isclose(float(sum_diag["category_sgp"]["R"]), 2.0)
    assert math.isclose(float(sum_diag["category_sgp"]["W"]), 4.0)

    max_mode = common_math.combine_two_way(hit_vals, pit_vals, two_way="max")
    max_diag = max_mode.iloc[0]["ReplacementDiagnostics"]
    assert max_diag["two_way_mode"] == "max"
    assert max_diag["selected_side"] == "pit"
    assert max_diag["best_slot"] == "P"


def test_build_calculation_explanations_includes_stat_dynasty_contributions() -> None:
    from backend.core.calculator_helpers import build_calculation_explanations

    out = pd.DataFrame([{
        "Player": "Test Player",
        "PlayerKey": "test-player",
        "EntityKey": "test-player",
        "Team": "AAA",
        "Pos": "1B",
        "DynastyValue": 10.0,
        "RawDynastyValue": 12.0,
        "Value_2026": 5.0,
        "Value_2027": 3.0,
        "StatDynasty_R": 3.0,
        "StatDynasty_HR": 4.0,
        "StatDynasty_AVG": 3.0,
    }])

    explanations = build_calculation_explanations(
        out,
        settings={"scoring_mode": "roto", "discount": 0.94},
        player_key_col="PlayerKey",
        player_entity_key_col="EntityKey",
        normalize_player_key_fn=lambda x: str(x).lower().replace(" ", "-"),
        numeric_or_zero_fn=lambda v: float(v) if v is not None and not pd.isna(v) else 0.0,
        value_col_sort_key_fn=lambda col: (0, int(col.split("_")[1]) if "_" in col else 0),
    )

    assert "test-player" in explanations
    ex = explanations["test-player"]
    assert "stat_dynasty_contributions" in ex
    assert math.isclose(ex["stat_dynasty_contributions"]["R"], 3.0)
    assert math.isclose(ex["stat_dynasty_contributions"]["HR"], 4.0)
    assert math.isclose(ex["stat_dynasty_contributions"]["AVG"], 3.0)


def test_build_calculation_explanations_no_stat_dynasty_for_points_mode() -> None:
    from backend.core.calculator_helpers import build_calculation_explanations

    out = pd.DataFrame([{
        "Player": "Test Player",
        "PlayerKey": "test-player",
        "EntityKey": "test-player",
        "Team": "AAA",
        "Pos": "1B",
        "DynastyValue": 10.0,
        "RawDynastyValue": 12.0,
        "Value_2026": 5.0,
        "StatDynasty_R": 3.0,
    }])

    explanations = build_calculation_explanations(
        out,
        settings={"scoring_mode": "points", "discount": 0.94},
        player_key_col="PlayerKey",
        player_entity_key_col="EntityKey",
        normalize_player_key_fn=lambda x: str(x).lower().replace(" ", "-"),
        numeric_or_zero_fn=lambda v: float(v) if v is not None and not pd.isna(v) else 0.0,
        value_col_sort_key_fn=lambda col: (0, int(col.split("_")[1]) if "_" in col else 0),
    )

    ex = explanations["test-player"]
    assert "stat_dynasty_contributions" not in ex


def test_build_calculation_explanations_include_centering_metadata() -> None:
    from backend.core.calculator_helpers import build_calculation_explanations

    out = pd.DataFrame([{
        "Player": "Test Player",
        "PlayerKey": "test-player",
        "EntityKey": "test-player",
        "Team": "AAA",
        "Pos": "1B",
        "DynastyValue": 1.8,
        "RawDynastyValue": 0.0,
        "CenteringMode": "forced_roster",
        "ForcedRosterFallbackApplied": True,
        "CenteringScore": -0.2,
        "ForcedRosterValue": -0.2,
        "CenteringBaselineValue": 0.0,
        "CenteringScoreBaselineValue": -2.0,
        "Value_2026": -1.5,
        "Value_2027": 2.0,
    }])

    explanations = build_calculation_explanations(
        out,
        settings={"scoring_mode": "roto", "discount": 0.94},
        player_key_col="PlayerKey",
        player_entity_key_col="EntityKey",
        normalize_player_key_fn=lambda x: str(x).lower().replace(" ", "-"),
        numeric_or_zero_fn=lambda v: float(v) if v is not None and not pd.isna(v) else 0.0,
        value_col_sort_key_fn=lambda col: (0, int(col.split("_")[1]) if "_" in col else 0),
    )

    ex = explanations["test-player"]
    assert ex["centering"]["mode"] == "forced_roster"
    assert ex["centering"]["fallback_applied"] is True
    assert math.isclose(ex["centering"]["score"], -0.2)
    assert math.isclose(ex["centering"]["baseline_value"], -2.0)
    assert math.isclose(ex["centering"]["raw_baseline_value"], 0.0)
    assert math.isclose(ex["centering"]["forced_roster_value"], -0.2)


def test_build_calculation_explanations_include_roto_adjustment_diagnostics() -> None:
    from backend.core.calculator_helpers import build_calculation_explanations

    out = pd.DataFrame([{
        "Player": "Corbin Carroll",
        "PlayerKey": "corbin-carroll",
        "EntityKey": "corbin-carroll",
        "Team": "ARI",
        "Pos": "OF",
        "DynastyValue": 4.0,
        "RawDynastyValue": 4.0,
        "Value_2026": 5.0,
        "_ExplainPlayerProfile": "hitter",
        "_ExplainCurrentYearVolume": {"ab": 510.0, "ip": 0.0},
        "_ExplainRiskFlags": {
            "playing_time_reliability_enabled": False,
            "age_risk_enabled": False,
            "prospect_risk_enabled": True,
        },
        "_ExplainRotoByYear": {
            "2026": {
                "raw_year_value": 5.0,
                "adjusted_year_value": 4.0,
                "after_risk_value": 4.0,
                "age_risk_multiplier": 1.0,
                "prospect_risk_multiplier": 0.8,
                "minor_eligible": True,
                "near_zero_playing_time": False,
                "can_minor_stash": False,
                "can_ir_stash": False,
                "can_bench_stash": False,
                "stash_adjustment_applied": False,
                "projected_ab": 510.0,
                "projected_ip": 0.0,
                "discount_factor": 1.0,
                "discounted_contribution": 4.0,
                "keep_drop_value": 4.0,
                "keep_drop_hold_value": 4.0,
                "keep_drop_keep": True,
                "best_slot": "OF",
                "replacement_value_diagnostics": {
                    "best_slot": "OF",
                    "category_sgp": {"R": 1.5, "SB": 1.0, "AVG": -0.25},
                    "slot_baseline_reference": {
                        "slot": "OF",
                        "volume": {"ab": 600.0, "ip": 0.0},
                        "components": {"AB": 600.0, "H": 160.0},
                    },
                    "replacement_reference": {
                        "slot": "OF",
                        "replacement_pool_depth": 36,
                        "replacement_depth_mode": "blended_depth",
                        "slot_count_per_team": 5,
                        "slot_capacity_league": 60,
                        "volume": {"ab": 520.0, "ip": 0.0},
                        "components": {"AB": 520.0, "H": 132.0},
                    },
                    "guard": {
                        "mode": "none",
                        "player_volume": 510.0,
                        "slot_volume_reference": 600.0,
                        "workload_share": 0.85,
                        "positive_credit_scale": 1.0,
                        "pre_guard_category_delta": {"R": 1.5, "SB": 1.0, "AVG": -0.25},
                        "post_guard_category_delta": {"R": 1.5, "SB": 1.0, "AVG": -0.25},
                    },
                },
            },
        },
    }])

    explanations = build_calculation_explanations(
        out,
        settings={"scoring_mode": "roto", "discount": 0.94},
        player_key_col="PlayerKey",
        player_entity_key_col="EntityKey",
        normalize_player_key_fn=lambda x: str(x).lower().replace(" ", "-"),
        numeric_or_zero_fn=lambda v: float(v) if v is not None and not pd.isna(v) else 0.0,
        value_col_sort_key_fn=lambda col: (0, int(col.split("_")[1]) if "_" in col else 0),
    )

    ex = explanations["corbin-carroll"]
    assert ex["profile"] == "hitter"
    assert math.isclose(ex["current_year_volume"]["ab"], 510.0)
    assert ex["risk_flags"]["prospect_risk_enabled"] is True
    year = ex["per_year"][0]
    assert math.isclose(year["raw_year_value"], 5.0)
    assert math.isclose(year["adjusted_year_value_before_discount"], 4.0)
    assert math.isclose(year["prospect_risk_multiplier"], 0.8)
    assert math.isclose(year["discounted_contribution"], 4.0)
    assert year["keep_drop_keep"] is True
    assert year["minor_eligible"] is True
    assert year["best_slot"] == "OF"
    assert math.isclose(year["category_sgp"]["R"], 1.5)
    assert ex["start_year_best_slot"] == "OF"
    assert ex["start_year_top_positive_categories"][0]["category"] == "R"
    assert ex["start_year_top_negative_categories"][0]["category"] == "AVG"
    assert math.isclose(ex["start_year_guard_summary"]["workload_share"], 0.85)
    assert ex["start_year_replacement_pool_depth"] == 36
    assert ex["start_year_replacement_depth_mode"] == "blended_depth"
    assert ex["start_year_slot_count_per_team"] == 5
    assert ex["start_year_slot_capacity_league"] == 60
    assert ex["start_year_replacement_reference"]["replacement_pool_depth"] == 36


def test_build_calculation_explanations_include_residual_minor_slot_metadata() -> None:
    from backend.core.calculator_helpers import build_calculation_explanations

    out = pd.DataFrame([{
        "Player": "Soon Prospect",
        "PlayerKey": "soon-prospect",
        "EntityKey": "soon-prospect",
        "Team": "AAA",
        "Pos": "OF",
        "DynastyValue": 0.036,
        "RawDynastyValue": 0.0,
        "CenteringMode": "forced_roster_minor_cost",
        "ForcedRosterFallbackApplied": True,
        "CenteringScore": -0.138,
        "ForcedRosterValue": 0.0,
        "CenteringBaselineValue": 0.0,
        "CenteringScoreBaselineValue": -0.174001,
        "MinorSlotCostValue": -0.138,
        "MinorEtaOffset": 1.0,
        "MinorProjectedVolumeScore": 10.0,
        "Value_2026": 0.0,
        "Value_2027": 0.0,
    }])

    explanations = build_calculation_explanations(
        out,
        settings={"scoring_mode": "roto", "discount": 0.94},
        player_key_col="PlayerKey",
        player_entity_key_col="EntityKey",
        normalize_player_key_fn=lambda x: str(x).lower().replace(" ", "-"),
        numeric_or_zero_fn=lambda v: float(v) if v is not None and not pd.isna(v) else 0.0,
        value_col_sort_key_fn=lambda col: (0, int(col.split("_")[1]) if "_" in col else 0),
    )

    ex = explanations["soon-prospect"]
    assert ex["centering"]["mode"] == "forced_roster_minor_cost"
    assert math.isclose(ex["centering"]["minor_slot_cost_value"], -0.138)
    assert ex["centering"]["minor_eta_offset"] == 1
    assert math.isclose(ex["centering"]["minor_projected_volume_score"], 10.0)


def test_common_active_volume_squeezes_identical_hitter_congestion() -> None:
    bat = pd.DataFrame(
        [
            {
                "Player": "OF A",
                "Year": 2026,
                "Team": "AAA",
                "Age": 27,
                "Pos": "OF",
                "G": 162.0,
                "AB": 600.0,
                "H": 180.0,
                "R": 90.0,
                "HR": 25.0,
                "RBI": 90.0,
                "SB": 10.0,
                "BB": 60.0,
                "HBP": 3.0,
                "SF": 4.0,
                "2B": 30.0,
                "3B": 2.0,
            },
            {
                "Player": "OF B",
                "Year": 2026,
                "Team": "AAA",
                "Age": 27,
                "Pos": "OF",
                "G": 162.0,
                "AB": 600.0,
                "H": 180.0,
                "R": 90.0,
                "HR": 25.0,
                "RBI": 90.0,
                "SB": 10.0,
                "BB": 60.0,
                "HBP": 3.0,
                "SF": 4.0,
                "2B": 30.0,
                "3B": 2.0,
            },
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
                "G": 30.0,
                "GS": 30.0,
                "IP": 170.0,
                "W": 12.0,
                "QS": 18.0,
                "QA3": 18.0,
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
    lg = CommonDynastyRotoSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"OF": 1},
        pitcher_slots={"P": 1},
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
    )

    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=19)
    usage_shares = sorted(float(value) for value in ctx["bat_y"]["_UsageShare"].tolist())

    assert math.isclose(float(usage_shares[0]), 6.0 / 162.0)
    assert math.isclose(float(usage_shares[1]), 1.0)
    assert math.isclose(float(ctx["hitter_usage_diagnostics"]["assigned_hitter_games"]), 168.0)
    assert int(ctx["hitter_usage_diagnostics"]["synthetic_season_days"]) == 182


def test_common_active_volume_prefers_multi_position_hitter() -> None:
    bat = pd.DataFrame(
        [
            {
                "Player": "Corner Lock",
                "Year": 2026,
                "Team": "AAA",
                "Age": 28,
                "Pos": "1B",
                "G": 162.0,
                "AB": 620.0,
                "H": 190.0,
                "R": 95.0,
                "HR": 30.0,
                "RBI": 105.0,
                "SB": 5.0,
                "BB": 65.0,
                "HBP": 4.0,
                "SF": 5.0,
                "2B": 32.0,
                "3B": 2.0,
            },
            {
                "Player": "Versatile Bat",
                "Year": 2026,
                "Team": "AAA",
                "Age": 26,
                "Pos": "1B/3B",
                "G": 162.0,
                "AB": 580.0,
                "H": 170.0,
                "R": 85.0,
                "HR": 24.0,
                "RBI": 90.0,
                "SB": 6.0,
                "BB": 58.0,
                "HBP": 3.0,
                "SF": 4.0,
                "2B": 28.0,
                "3B": 2.0,
            },
            {
                "Player": "First Base Bench",
                "Year": 2026,
                "Team": "AAA",
                "Age": 26,
                "Pos": "1B",
                "G": 162.0,
                "AB": 580.0,
                "H": 170.0,
                "R": 85.0,
                "HR": 24.0,
                "RBI": 90.0,
                "SB": 6.0,
                "BB": 58.0,
                "HBP": 3.0,
                "SF": 4.0,
                "2B": 28.0,
                "3B": 2.0,
            },
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
                "G": 30.0,
                "GS": 30.0,
                "IP": 170.0,
                "W": 12.0,
                "QS": 18.0,
                "QA3": 18.0,
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
    lg = CommonDynastyRotoSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"1B": 1, "3B": 1},
        pitcher_slots={"P": 1},
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
    )

    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=23)
    bat_y = ctx["bat_y"].set_index("Player")

    assert math.isclose(float(bat_y.loc["Corner Lock", "_UsageShare"]), 1.0)
    assert math.isclose(float(bat_y.loc["Versatile Bat", "_UsageShare"]), 1.0)
    assert math.isclose(float(bat_y.loc["First Base Bench", "_UsageShare"]), 20.0 / 162.0)
    assert float(bat_y.loc["Versatile Bat", "_UsageShare"]) > float(bat_y.loc["First Base Bench", "_UsageShare"])


def test_common_active_volume_missing_games_falls_back_to_full_utilization() -> None:
    bat = pd.DataFrame(
        [
            {
                "Player": "Fallback Bat",
                "Year": 2026,
                "Team": "AAA",
                "Age": 25,
                "Pos": "UT",
                "AB": 500.0,
                "H": 150.0,
                "R": 80.0,
                "HR": 20.0,
                "RBI": 85.0,
                "SB": 8.0,
                "BB": 55.0,
                "HBP": 2.0,
                "SF": 4.0,
                "2B": 25.0,
                "3B": 1.0,
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
                "G": 30.0,
                "GS": 30.0,
                "IP": 170.0,
                "W": 12.0,
                "QS": 18.0,
                "QA3": 18.0,
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
    lg = CommonDynastyRotoSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"UT": 1},
        pitcher_slots={"P": 1},
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
    )

    ctx = common_math.compute_year_context(2026, bat, pit, lg, rng_seed=29)
    row = ctx["bat_y"].iloc[0]

    assert math.isclose(float(row["_UsageShare"]), 1.0)
    assert math.isclose(float(row["AB"]), 500.0)
    assert int(ctx["hitter_usage_diagnostics"]["fallback_hitter_count"]) == 1
