"""Unit tests for backend.valuation.positions — position parsing & slot eligibility."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.valuation.positions import (
    eligible_hit_slots,
    eligible_pit_slots,
    parse_hit_positions,
    parse_pit_positions,
)

pytestmark = pytest.mark.valuation

# ---------------------------------------------------------------------------
# parse_hit_positions
# ---------------------------------------------------------------------------

class TestParseHitPositions:
    def test_simple_single_position(self):
        assert parse_hit_positions("1B") == {"1B"}

    def test_slash_separated(self):
        assert parse_hit_positions("1B/3B") == {"1B", "3B"}

    def test_outfield_aliases_collapse_to_of(self):
        assert parse_hit_positions("LF/CF/RF") == {"OF"}

    def test_dh_remains_distinct(self):
        assert parse_hit_positions("DH") == {"DH"}

    def test_util_aliases_to_ut(self):
        assert parse_hit_positions("UTIL") == {"UT"}

    def test_u_aliases_to_ut(self):
        assert parse_hit_positions("U") == {"UT"}

    def test_mixed_positions_with_aliases(self):
        result = parse_hit_positions("1B/LF/DH")
        assert result == {"1B", "OF", "DH"}

    def test_lowercase_normalized(self):
        assert parse_hit_positions("ss") == {"SS"}

    def test_mixed_case(self):
        assert parse_hit_positions("Ss/Of") == {"SS", "OF"}

    def test_empty_string(self):
        assert parse_hit_positions("") == set()

    def test_nan(self):
        assert parse_hit_positions(float("nan")) == set()

    def test_pd_nan(self):
        assert parse_hit_positions(pd.NA) == set()

    def test_multiple_delimiters(self):
        assert parse_hit_positions("1B, 3B") == {"1B", "3B"}
        assert parse_hit_positions("1B|3B") == {"1B", "3B"}

    def test_space_delimiter(self):
        assert parse_hit_positions("1B 3B") == {"1B", "3B"}

    def test_double_slash(self):
        # Double delimiter should not produce empty tokens
        result = parse_hit_positions("1B//3B")
        assert "" not in result
        assert "1B" in result and "3B" in result

    def test_catcher(self):
        assert parse_hit_positions("C") == {"C"}


# ---------------------------------------------------------------------------
# eligible_hit_slots
# ---------------------------------------------------------------------------

class TestEligibleHitSlots:
    def test_empty_returns_empty(self):
        assert eligible_hit_slots(set()) == set()

    def test_first_base_gets_ci_and_ut(self):
        result = eligible_hit_slots({"1B"})
        assert result == {"1B", "CI", "UT"}

    def test_third_base_gets_ci_and_ut(self):
        result = eligible_hit_slots({"3B"})
        assert result == {"3B", "CI", "UT"}

    def test_second_base_gets_mi_and_ut(self):
        result = eligible_hit_slots({"2B"})
        assert result == {"2B", "MI", "UT"}

    def test_shortstop_gets_mi_and_ut(self):
        result = eligible_hit_slots({"SS"})
        assert result == {"SS", "MI", "UT"}

    def test_catcher_gets_c_and_ut(self):
        result = eligible_hit_slots({"C"})
        assert result == {"C", "UT"}

    def test_outfield_gets_of_and_ut(self):
        result = eligible_hit_slots({"OF"})
        assert result == {"OF", "UT"}

    def test_dh_gets_dh_and_ut(self):
        result = eligible_hit_slots({"DH"})
        assert result == {"DH", "UT"}

    def test_multi_position_combines_slots(self):
        result = eligible_hit_slots({"1B", "3B"})
        assert result == {"1B", "3B", "CI", "UT"}

    def test_first_base_plus_dh_combines_slots(self):
        result = eligible_hit_slots({"1B", "DH"})
        assert result == {"1B", "CI", "DH", "UT"}

    def test_corner_plus_middle(self):
        result = eligible_hit_slots({"1B", "SS"})
        assert result == {"1B", "CI", "SS", "MI", "UT"}

    def test_ci_token_adds_ci(self):
        result = eligible_hit_slots({"CI"})
        assert "CI" in result

    def test_mi_token_adds_mi(self):
        result = eligible_hit_slots({"MI"})
        assert "MI" in result


# ---------------------------------------------------------------------------
# parse_pit_positions
# ---------------------------------------------------------------------------

class TestParsePitPositions:
    def test_sp(self):
        assert parse_pit_positions("SP") == {"SP"}

    def test_rp(self):
        assert parse_pit_positions("RP") == {"RP"}

    def test_rhp_aliases_to_sp(self):
        assert parse_pit_positions("RHP") == {"SP"}

    def test_lhp_aliases_to_sp(self):
        assert parse_pit_positions("LHP") == {"SP"}

    def test_sp_rp(self):
        assert parse_pit_positions("SP/RP") == {"SP", "RP"}

    def test_empty(self):
        assert parse_pit_positions("") == set()

    def test_nan(self):
        assert parse_pit_positions(float("nan")) == set()


# ---------------------------------------------------------------------------
# eligible_pit_slots
# ---------------------------------------------------------------------------

class TestEligiblePitSlots:
    def test_empty(self):
        assert eligible_pit_slots(set()) == set()

    def test_sp_gets_sp_and_p(self):
        result = eligible_pit_slots({"SP"})
        assert result == {"SP", "P"}

    def test_rp_gets_rp_and_p(self):
        result = eligible_pit_slots({"RP"})
        assert result == {"RP", "P"}

    def test_sp_rp_gets_all(self):
        result = eligible_pit_slots({"SP", "RP"})
        assert result == {"SP", "RP", "P"}

