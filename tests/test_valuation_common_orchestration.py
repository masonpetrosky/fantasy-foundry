"""Unit tests for backend.valuation.common_orchestration — helper functions."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.valuation.common_orchestration import (
    _blend_replacement_frame,
    _piecewise_age_factor,
    _position_profile,
    _year_risk_multiplier,
)

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
