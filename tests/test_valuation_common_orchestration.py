"""Unit tests for backend.valuation.common_orchestration — helper functions."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.valuation.common_orchestration import (
    _adjust_dynasty_year_value,
    _apply_dynasty_centering,
    _blend_replacement_frame,
    _forced_roster_value,
    _piecewise_age_factor,
    _position_profile,
    _prospect_risk_multiplier,
    _year_risk_multiplier,
)
from backend.valuation.models import CommonDynastyRotoSettings

pytestmark = pytest.mark.valuation

# ---------------------------------------------------------------------------
# _position_profile
# ---------------------------------------------------------------------------

class TestPositionProfile:
    def test_empty_string(self):
        assert _position_profile("") == "hitter"

    def test_none(self):
        assert _position_profile(None) == "hitter"

    def test_hitter_positions(self):
        assert _position_profile("1B") == "hitter"
        assert _position_profile("SS") == "hitter"
        assert _position_profile("OF") == "hitter"
        assert _position_profile("DH") == "hitter"

    def test_catcher_position(self):
        assert _position_profile("C") == "catcher"

    def test_pitcher_sp(self):
        assert _position_profile("SP") == "pitcher"

    def test_pitcher_rp(self):
        assert _position_profile("RP") == "pitcher"

    def test_pitcher_p(self):
        assert _position_profile("P") == "pitcher"

    def test_pitcher_combo(self):
        assert _position_profile("SP/RP") == "pitcher"

    def test_two_way(self):
        assert _position_profile("SP/1B") == "two_way"
        assert _position_profile("OF/RP") == "two_way"

    def test_case_insensitive(self):
        assert _position_profile("sp") == "pitcher"
        assert _position_profile("Sp/Of") == "two_way"

    def test_multiple_delimiters(self):
        assert _position_profile("SP, RP") == "pitcher"
        assert _position_profile("1B|SP") == "two_way"
        assert _position_profile("SS;2B") == "hitter"

    def test_multi_position_hitter(self):
        assert _position_profile("1B/3B/OF") == "hitter"

    def test_whitespace_only(self):
        assert _position_profile("   ") == "hitter"


# ---------------------------------------------------------------------------
# _piecewise_age_factor
# ---------------------------------------------------------------------------

class TestPiecewiseAgeFactor:
    # -- Pitcher curve --
    def test_pitcher_young(self):
        assert _piecewise_age_factor(25.0, profile="pitcher") == 1.0

    def test_pitcher_at_28(self):
        assert _piecewise_age_factor(28.0, profile="pitcher") == 1.0

    def test_pitcher_midrange_31(self):
        # Linear interpolation: 1.0 + (0.84 - 1.0) * ((31 - 28) / 6) = 1.0 - 0.08 = 0.92
        result = _piecewise_age_factor(31.0, profile="pitcher")
        assert result == pytest.approx(0.92, abs=1e-6)

    def test_pitcher_at_34(self):
        result = _piecewise_age_factor(34.0, profile="pitcher")
        assert result == pytest.approx(0.84, abs=1e-6)

    def test_pitcher_midrange_36(self):
        # 0.84 + (0.70 - 0.84) * ((36 - 34) / 4) = 0.84 - 0.07 = 0.77
        result = _piecewise_age_factor(36.0, profile="pitcher")
        assert result == pytest.approx(0.77, abs=1e-6)

    def test_pitcher_at_38(self):
        result = _piecewise_age_factor(38.0, profile="pitcher")
        assert result == pytest.approx(0.70, abs=1e-6)

    def test_pitcher_old(self):
        assert _piecewise_age_factor(42.0, profile="pitcher") == 0.70

    # -- Hitter curve --
    def test_hitter_young(self):
        assert _piecewise_age_factor(25.0, profile="hitter") == 1.0

    def test_hitter_at_29(self):
        assert _piecewise_age_factor(29.0, profile="hitter") == 1.0

    def test_hitter_midrange_32(self):
        # 1.0 + (0.88 - 1.0) * ((32 - 29) / 6) = 1.0 - 0.06 = 0.94
        result = _piecewise_age_factor(32.0, profile="hitter")
        assert result == pytest.approx(0.94, abs=1e-6)

    def test_hitter_at_35(self):
        result = _piecewise_age_factor(35.0, profile="hitter")
        assert result == pytest.approx(0.88, abs=1e-6)

    def test_hitter_midrange_37(self):
        # 0.88 + (0.75 - 0.88) * ((37 - 35) / 4) = 0.88 - 0.065 = 0.815
        result = _piecewise_age_factor(37.0, profile="hitter")
        assert result == pytest.approx(0.815, abs=1e-6)

    def test_hitter_at_39(self):
        result = _piecewise_age_factor(39.0, profile="hitter")
        assert result == pytest.approx(0.75, abs=1e-6)

    def test_hitter_old(self):
        assert _piecewise_age_factor(42.0, profile="hitter") == 0.75

    # -- Two-way uses hitter curve --
    def test_two_way_uses_hitter_curve(self):
        assert _piecewise_age_factor(25.0, profile="two_way") == 1.0
        assert _piecewise_age_factor(42.0, profile="two_way") == 0.75


# ---------------------------------------------------------------------------
# _year_risk_multiplier
# ---------------------------------------------------------------------------

class TestYearRiskMultiplier:
    def test_disabled_returns_one(self):
        result = _year_risk_multiplier(
            age_start=30.0, year=2028, start_year=2026,
            profile="hitter", enabled=False,
        )
        assert result == 1.0

    def test_none_age_returns_one(self):
        result = _year_risk_multiplier(
            age_start=None, year=2028, start_year=2026,
            profile="hitter", enabled=True,
        )
        assert result == 1.0

    def test_nan_age_returns_one(self):
        result = _year_risk_multiplier(
            age_start=float("nan"), year=2028, start_year=2026,
            profile="hitter", enabled=True,
        )
        assert result == 1.0

    def test_inf_age_returns_one(self):
        result = _year_risk_multiplier(
            age_start=float("inf"), year=2028, start_year=2026,
            profile="hitter", enabled=True,
        )
        assert result == 1.0

    def test_young_hitter_no_decay(self):
        # Age 25 in start year, year+2 → age 27, still ≤ 29 → factor=1.0, age < 31 → no 0.98 decay
        result = _year_risk_multiplier(
            age_start=25.0, year=2028, start_year=2026,
            profile="hitter", enabled=True,
        )
        assert result == 1.0

    def test_same_year_no_offset(self):
        result = _year_risk_multiplier(
            age_start=35.0, year=2026, start_year=2026,
            profile="hitter", enabled=True,
        )
        # age=35, year_offset=0, factor = piecewise(35, hitter) = 0.88
        # age >= 31 but year_offset == 0, so no 0.98 decay
        assert result == pytest.approx(0.88, abs=1e-6)

    def test_older_hitter_with_decay(self):
        # age_start=32, year=2028, start=2026 → offset=2, age=34
        # piecewise(34, hitter) = 1.0 + (0.88-1.0)*((34-29)/6) = 1.0 - 0.1 = 0.9
        # age=34 >= 31 and offset=2 → factor *= 0.98^2 = 0.9604
        # final = 0.9 * 0.9604 = 0.86436
        result = _year_risk_multiplier(
            age_start=32.0, year=2028, start_year=2026,
            profile="hitter", enabled=True,
        )
        expected = (1.0 + (0.88 - 1.0) * (5.0 / 6.0)) * (0.98 ** 2)
        assert result == pytest.approx(expected, abs=1e-6)

    def test_pitcher_age_decay(self):
        # age_start=30, year=2030, start=2026 → offset=4, age=34
        # piecewise(34, pitcher) = 0.84
        # age >= 31 and offset=4 → factor *= 0.98^4
        result = _year_risk_multiplier(
            age_start=30.0, year=2030, start_year=2026,
            profile="pitcher", enabled=True,
        )
        expected = 0.84 * (0.98 ** 4)
        assert result == pytest.approx(expected, abs=1e-6)

    def test_clamped_to_zero_one(self):
        # Very old pitcher, many years out — should never go negative
        result = _year_risk_multiplier(
            age_start=40.0, year=2046, start_year=2026,
            profile="pitcher", enabled=True,
        )
        assert 0.0 <= result <= 1.0

    def test_year_before_start_no_negative_offset(self):
        # year < start_year → offset = max(0, ...) = 0
        result = _year_risk_multiplier(
            age_start=30.0, year=2025, start_year=2026,
            profile="hitter", enabled=True,
        )
        # offset=0, age=30, piecewise(30, hitter) = 1.0 + (0.88-1.0)*((30-29)/6) = ~0.98
        assert result == pytest.approx(1.0 + (0.88 - 1.0) * (1.0 / 6.0), abs=1e-6)


# ---------------------------------------------------------------------------
# _prospect_risk_multiplier / _adjust_dynasty_year_value
# ---------------------------------------------------------------------------

class TestProspectRiskMultiplier:
    def test_disabled_returns_one(self):
        assert _prospect_risk_multiplier(
            year=2028,
            start_year=2026,
            profile="hitter",
            minor_eligible=True,
            enabled=False,
        ) == 1.0

    def test_non_minor_returns_one(self):
        assert _prospect_risk_multiplier(
            year=2028,
            start_year=2026,
            profile="hitter",
            minor_eligible=False,
            enabled=True,
        ) == 1.0

    def test_hitter_discount_compounds_by_year(self):
        assert _prospect_risk_multiplier(
            year=2028,
            start_year=2026,
            profile="hitter",
            minor_eligible=True,
            enabled=True,
        ) == pytest.approx(0.92 ** 2)

    def test_pitcher_discount_respects_floor(self):
        assert _prospect_risk_multiplier(
            year=2034,
            start_year=2026,
            profile="pitcher",
            minor_eligible=True,
            enabled=True,
        ) == pytest.approx(0.45)


class TestAdjustDynastyYearValue:
    def test_positive_minor_eligible_value_gets_prospect_discount(self):
        lg = CommonDynastyRotoSettings(enable_prospect_risk_adjustment=True)
        adjusted = _adjust_dynasty_year_value(
            10.0,
            player="Prospect",
            year=2028,
            start_year=2026,
            age_start=22.0,
            profile="hitter",
            lg=lg,
            minor_eligibility_by_year={("Prospect", 2028): True},
            minor_stash_players=set(),
            bench_stash_players=set(),
            ir_stash_players=set(),
            hitter_ab_by_player_year={("Prospect", 2028): 150.0},
            pitcher_ip_by_player_year={},
        )
        assert adjusted == pytest.approx(10.0 * (0.92 ** 2))

    def test_negative_values_follow_minor_ir_then_bench_stash_paths(self):
        lg = CommonDynastyRotoSettings(
            enable_prospect_risk_adjustment=True,
            enable_bench_stash_relief=True,
            bench_negative_penalty=0.5,
            enable_ir_stash_relief=True,
            ir_negative_penalty=0.25,
        )

        minor_adjusted = _adjust_dynasty_year_value(
            -10.0,
            player="Prospect",
            year=2028,
            start_year=2026,
            age_start=22.0,
            profile="hitter",
            lg=lg,
            minor_eligibility_by_year={("Prospect", 2028): True},
            minor_stash_players={"Prospect"},
            bench_stash_players=set(),
            ir_stash_players=set(),
            hitter_ab_by_player_year={("Prospect", 2028): 0.0},
            pitcher_ip_by_player_year={},
        )
        assert minor_adjusted == 0.0

        ir_adjusted = _adjust_dynasty_year_value(
            -8.0,
            player="Injured Vet",
            year=2027,
            start_year=2026,
            age_start=31.0,
            profile="hitter",
            lg=lg,
            minor_eligibility_by_year={},
            minor_stash_players=set(),
            bench_stash_players=set(),
            ir_stash_players={"Injured Vet"},
            hitter_ab_by_player_year={("Injured Vet", 2027): 0.0},
            pitcher_ip_by_player_year={},
        )
        assert ir_adjusted == pytest.approx(-2.0)

        bench_adjusted = _adjust_dynasty_year_value(
            -6.0,
            player="Bench Bat",
            year=2027,
            start_year=2026,
            age_start=28.0,
            profile="hitter",
            lg=lg,
            minor_eligibility_by_year={},
            minor_stash_players=set(),
            bench_stash_players={"Bench Bat"},
            ir_stash_players=set(),
            hitter_ab_by_player_year={("Bench Bat", 2027): 250.0},
            pitcher_ip_by_player_year={},
        )
        assert bench_adjusted == pytest.approx(-3.0)


class TestForcedRosterValue:
    def test_empty_inputs_return_zero(self):
        assert _forced_roster_value([], [], 0.94) == 0.0

    def test_single_year_returns_year_value_without_drop_floor(self):
        assert _forced_roster_value([-2.5], [2026], 0.94) == pytest.approx(-2.5)

    def test_negative_now_positive_later_keeps_future_salvage(self):
        result = _forced_roster_value([-3.0, 8.0], [2026, 2027], 0.94)
        assert result == pytest.approx(-3.0 + (0.94 * 8.0))


class TestApplyDynastyCentering:
    def test_forced_roster_fallback_separates_raw_zero_cluster(self):
        out = pd.DataFrame(
            [
                {"Player": "A", "RawDynastyValue": 10.0},
                {"Player": "B", "RawDynastyValue": 8.0},
                {"Player": "C", "RawDynastyValue": 0.0},
                {"Player": "D", "RawDynastyValue": 0.0},
                {"Player": "E", "RawDynastyValue": 0.0},
                {"Player": "F", "RawDynastyValue": 0.0},
            ]
        )

        centered, diagnostics = _apply_dynasty_centering(
            out,
            forced_roster_values=[10.0, 8.0, -0.2, -1.0, -2.0, -3.0],
            total_minor_slots=0,
            total_ir_slots=0,
            total_bench_slots=0,
            total_active_slots=5,
            active_floor_names=set(),
            minor_candidate_players=set(),
            ir_candidate_players=set(),
            bench_candidate_players=set(),
        )

        by_player = centered.set_index("Player")
        assert diagnostics["CenteringMode"] == "forced_roster"
        assert diagnostics["ForcedRosterFallbackApplied"] is True
        assert diagnostics["CenteringBaselineValue"] == pytest.approx(0.0)
        assert diagnostics["CenteringScoreBaselineValue"] == pytest.approx(-2.0)
        assert diagnostics["RawZeroValuePlayerCount"] == 4
        assert diagnostics["DynastyZeroValuePlayerCount"] == 1
        assert diagnostics["deep_roster_zero_baseline_warning"] is True
        assert by_player.loc["C", "DynastyValue"] == pytest.approx(1.8)
        assert by_player.loc["D", "DynastyValue"] == pytest.approx(1.0)
        assert by_player.loc["E", "DynastyValue"] == pytest.approx(0.0)
        assert by_player.loc["F", "DynastyValue"] == pytest.approx(-1.0)

    def test_standard_mode_keeps_raw_baseline_centering(self):
        out = pd.DataFrame(
            [
                {"Player": "A", "RawDynastyValue": 10.0},
                {"Player": "B", "RawDynastyValue": 8.0},
                {"Player": "C", "RawDynastyValue": 5.0},
                {"Player": "D", "RawDynastyValue": 4.0},
            ]
        )

        centered, diagnostics = _apply_dynasty_centering(
            out,
            forced_roster_values=[10.0, 8.0, 5.0, 4.0],
            total_minor_slots=0,
            total_ir_slots=0,
            total_bench_slots=0,
            total_active_slots=3,
            active_floor_names=set(),
            minor_candidate_players=set(),
            ir_candidate_players=set(),
            bench_candidate_players=set(),
        )

        by_player = centered.set_index("Player")
        assert diagnostics["CenteringMode"] == "standard"
        assert diagnostics["ForcedRosterFallbackApplied"] is False
        assert diagnostics["CenteringBaselineValue"] == pytest.approx(5.0)
        assert diagnostics["CenteringScoreBaselineValue"] == pytest.approx(5.0)
        assert diagnostics["RawZeroValuePlayerCount"] == 0
        assert diagnostics["DynastyZeroValuePlayerCount"] == 1
        assert diagnostics["deep_roster_zero_baseline_warning"] is False
        assert by_player.loc["A", "DynastyValue"] == pytest.approx(5.0)
        assert by_player.loc["B", "DynastyValue"] == pytest.approx(3.0)
        assert by_player.loc["C", "DynastyValue"] == pytest.approx(0.0)

    def test_residual_minor_slot_cost_applies_when_forced_roster_cutoff_stays_zero(self):
        out = pd.DataFrame(
            [
                {"Player": "A", "RawDynastyValue": 10.0, "minor_eligible": False},
                {"Player": "B", "RawDynastyValue": 8.0, "minor_eligible": False},
                {"Player": "Soon Prospect", "RawDynastyValue": 0.0, "minor_eligible": True},
                {"Player": "Later Prospect", "RawDynastyValue": 0.0, "minor_eligible": True},
                {"Player": "Vet Edge", "RawDynastyValue": 0.0, "minor_eligible": False},
                {"Player": "Vet Tail", "RawDynastyValue": 0.0, "minor_eligible": False},
            ]
        )

        centered, diagnostics = _apply_dynasty_centering(
            out,
            forced_roster_values=[10.0, 8.0, 0.0, 0.0, -0.5, -1.0],
            total_minor_slots=0,
            total_ir_slots=0,
            total_bench_slots=0,
            total_active_slots=4,
            active_floor_names=set(),
            minor_candidate_players={"Soon Prospect", "Later Prospect"},
            ir_candidate_players=set(),
            bench_candidate_players=set(),
            n_teams=1,
            years=[2026, 2027],
            start_year=2026,
            hitter_ab_by_player_year={
                ("Soon Prospect", 2027): 10.0,
            },
            pitcher_ip_by_player_year={},
        )

        by_player = centered.set_index("Player")
        assert diagnostics["CenteringMode"] == "forced_roster_minor_cost"
        assert diagnostics["ForcedRosterFallbackApplied"] is True
        assert diagnostics["ResidualMinorSlotCostApplied"] is True
        assert diagnostics["ResidualZeroMinorCandidateCount"] == 2
        assert diagnostics["CenteringBaselineValue"] == pytest.approx(0.0)
        assert diagnostics["CenteringScoreBaselineValue"] == pytest.approx(
            float(by_player.loc["Later Prospect", "MinorSlotCostValue"])
        )
        assert diagnostics["CenteringScoreBaselineValue"] < 0.0
        assert diagnostics["CenteringScoreZeroPlayerCount"] == 0
        assert by_player.loc["Soon Prospect", "MinorEtaOffset"] == pytest.approx(1.0)
        assert by_player.loc["Soon Prospect", "MinorProjectedVolumeScore"] == pytest.approx(10.0)
        assert by_player.loc["Soon Prospect", "MinorSlotCostValue"] > by_player.loc["Later Prospect", "MinorSlotCostValue"]
        assert by_player.loc["Soon Prospect", "DynastyValue"] > 0.0
        assert by_player.loc["Later Prospect", "DynastyValue"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _blend_replacement_frame
# ---------------------------------------------------------------------------

class TestBlendReplacementFrame:
    def test_alpha_one_returns_frozen(self):
        frozen = pd.DataFrame({"A": [10.0]}, index=[0])
        current = pd.DataFrame({"A": [20.0]}, index=[0])
        result = _blend_replacement_frame(frozen, current, alpha=1.0)
        assert result["A"].iloc[0] == pytest.approx(10.0)

    def test_alpha_zero_returns_current(self):
        frozen = pd.DataFrame({"A": [10.0]}, index=[0])
        current = pd.DataFrame({"A": [20.0]}, index=[0])
        result = _blend_replacement_frame(frozen, current, alpha=0.0)
        assert result["A"].iloc[0] == pytest.approx(20.0)

    def test_alpha_half_returns_average(self):
        frozen = pd.DataFrame({"A": [10.0]}, index=[0])
        current = pd.DataFrame({"A": [20.0]}, index=[0])
        result = _blend_replacement_frame(frozen, current, alpha=0.5)
        assert result["A"].iloc[0] == pytest.approx(15.0)

    def test_mismatched_indices(self):
        frozen = pd.DataFrame({"A": [10.0]}, index=[0])
        current = pd.DataFrame({"A": [20.0]}, index=[1])
        result = _blend_replacement_frame(frozen, current, alpha=0.5)
        # index 0: frozen has 10, current has 0 (fillna) → 0.5*10 + 0.5*0 = 5
        # index 1: frozen has 0 (fillna), current has 20 → 0.5*0 + 0.5*20 = 10
        assert result.loc[0, "A"] == pytest.approx(5.0)
        assert result.loc[1, "A"] == pytest.approx(10.0)

    def test_mismatched_columns(self):
        frozen = pd.DataFrame({"A": [10.0]}, index=[0])
        current = pd.DataFrame({"B": [20.0]}, index=[0])
        result = _blend_replacement_frame(frozen, current, alpha=0.5)
        assert result.loc[0, "A"] == pytest.approx(5.0)
        assert result.loc[0, "B"] == pytest.approx(10.0)

    def test_multi_row_multi_col(self):
        frozen = pd.DataFrame({"X": [1.0, 2.0], "Y": [3.0, 4.0]})
        current = pd.DataFrame({"X": [5.0, 6.0], "Y": [7.0, 8.0]})
        result = _blend_replacement_frame(frozen, current, alpha=0.7)
        # X[0]: 0.7*1 + 0.3*5 = 2.2
        # Y[1]: 0.7*4 + 0.3*8 = 5.2
        assert result.loc[0, "X"] == pytest.approx(2.2)
        assert result.loc[1, "Y"] == pytest.approx(5.2)

    def test_default_alpha_range(self):
        frozen = pd.DataFrame({"A": [100.0]})
        current = pd.DataFrame({"A": [0.0]})
        result = _blend_replacement_frame(frozen, current, alpha=0.70)
        assert result["A"].iloc[0] == pytest.approx(70.0)
