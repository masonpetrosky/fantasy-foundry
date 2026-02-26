"""Unit tests for backend.valuation.league_orchestration — helper functions."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.valuation.league_orchestration import (
    _blend_replacement_frame,
    _piecewise_age_factor,
    _position_profile,
    _year_risk_multiplier,
)

# ---------------------------------------------------------------------------
# _position_profile  (league copy — verify identical behaviour)
# ---------------------------------------------------------------------------

class TestPositionProfile:
    def test_empty_and_none(self):
        assert _position_profile("") == "hitter"
        assert _position_profile(None) == "hitter"

    def test_hitter(self):
        assert _position_profile("1B") == "hitter"
        assert _position_profile("C/DH") == "hitter"

    def test_pitcher(self):
        assert _position_profile("SP") == "pitcher"
        assert _position_profile("RP") == "pitcher"
        assert _position_profile("SP/RP") == "pitcher"

    def test_two_way(self):
        assert _position_profile("SP/OF") == "two_way"

    def test_whitespace(self):
        assert _position_profile("  ") == "hitter"


# ---------------------------------------------------------------------------
# _piecewise_age_factor  (league copy — spot-check key breakpoints)
# ---------------------------------------------------------------------------

class TestPiecewiseAgeFactor:
    def test_pitcher_breakpoints(self):
        assert _piecewise_age_factor(28.0, profile="pitcher") == 1.0
        assert _piecewise_age_factor(34.0, profile="pitcher") == pytest.approx(0.84)
        assert _piecewise_age_factor(38.0, profile="pitcher") == pytest.approx(0.70)
        assert _piecewise_age_factor(42.0, profile="pitcher") == 0.70

    def test_hitter_breakpoints(self):
        assert _piecewise_age_factor(29.0, profile="hitter") == 1.0
        assert _piecewise_age_factor(35.0, profile="hitter") == pytest.approx(0.88)
        assert _piecewise_age_factor(39.0, profile="hitter") == pytest.approx(0.75)
        assert _piecewise_age_factor(42.0, profile="hitter") == 0.75

    def test_two_way_same_as_hitter(self):
        for age in [25.0, 32.0, 37.0, 42.0]:
            assert _piecewise_age_factor(age, profile="two_way") == _piecewise_age_factor(age, profile="hitter")


# ---------------------------------------------------------------------------
# _year_risk_multiplier  (league copy — verify key scenarios)
# ---------------------------------------------------------------------------

class TestYearRiskMultiplier:
    def test_disabled(self):
        assert _year_risk_multiplier(
            age_start=35.0, year=2030, start_year=2026,
            profile="hitter", enabled=False,
        ) == 1.0

    def test_none_age(self):
        assert _year_risk_multiplier(
            age_start=None, year=2028, start_year=2026,
            profile="hitter", enabled=True,
        ) == 1.0

    def test_nan_age(self):
        assert _year_risk_multiplier(
            age_start=float("nan"), year=2028, start_year=2026,
            profile="hitter", enabled=True,
        ) == 1.0

    def test_young_no_decay(self):
        assert _year_risk_multiplier(
            age_start=22.0, year=2028, start_year=2026,
            profile="hitter", enabled=True,
        ) == 1.0

    def test_old_pitcher_decays(self):
        result = _year_risk_multiplier(
            age_start=30.0, year=2030, start_year=2026,
            profile="pitcher", enabled=True,
        )
        # age=34, offset=4 → 0.84 * 0.98^4
        assert result == pytest.approx(0.84 * (0.98 ** 4), abs=1e-6)

    def test_result_in_zero_one(self):
        result = _year_risk_multiplier(
            age_start=40.0, year=2045, start_year=2026,
            profile="pitcher", enabled=True,
        )
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# _blend_replacement_frame  (league copy — verify core blending)
# ---------------------------------------------------------------------------

class TestBlendReplacementFrame:
    def test_full_frozen(self):
        f = pd.DataFrame({"A": [10.0]})
        c = pd.DataFrame({"A": [0.0]})
        result = _blend_replacement_frame(f, c, alpha=1.0)
        assert result["A"].iloc[0] == pytest.approx(10.0)

    def test_full_current(self):
        f = pd.DataFrame({"A": [10.0]})
        c = pd.DataFrame({"A": [0.0]})
        result = _blend_replacement_frame(f, c, alpha=0.0)
        assert result["A"].iloc[0] == pytest.approx(0.0)

    def test_even_blend(self):
        f = pd.DataFrame({"A": [10.0]})
        c = pd.DataFrame({"A": [30.0]})
        result = _blend_replacement_frame(f, c, alpha=0.5)
        assert result["A"].iloc[0] == pytest.approx(20.0)

    def test_mismatched_shapes(self):
        f = pd.DataFrame({"A": [1.0]}, index=[0])
        c = pd.DataFrame({"B": [2.0]}, index=[1])
        result = _blend_replacement_frame(f, c, alpha=0.5)
        # Both missing values filled with 0 before blend
        assert result.shape == (2, 2)
        assert result.loc[0, "A"] == pytest.approx(0.5)
        assert result.loc[1, "B"] == pytest.approx(1.0)
