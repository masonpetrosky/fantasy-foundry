"""Unit tests for backend.valuation.assignment — slot expansion, building, and player assignment."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.valuation.assignment import (
    assign_players_to_slots,
    build_slot_list,
    build_team_slot_template,
    expand_slot_counts,
    validate_assigned_slots,
)
from backend.valuation.positions import eligible_hit_slots, eligible_pit_slots

# ---------------------------------------------------------------------------
# expand_slot_counts
# ---------------------------------------------------------------------------

class TestExpandSlotCounts:
    def test_basic_expansion(self):
        result = expand_slot_counts({"C": 1, "1B": 1}, 12)
        assert result == {"C": 12, "1B": 12}

    def test_single_team(self):
        result = expand_slot_counts({"SP": 3}, 1)
        assert result == {"SP": 3}

    def test_empty_slots(self):
        result = expand_slot_counts({}, 12)
        assert result == {}


# ---------------------------------------------------------------------------
# build_slot_list
# ---------------------------------------------------------------------------

class TestBuildSlotList:
    def test_basic(self):
        result = build_slot_list({"C": 2, "1B": 1})
        assert sorted(result) == sorted(["C", "C", "1B"])

    def test_empty(self):
        assert build_slot_list({}) == []

    def test_zero_count_slot(self):
        result = build_slot_list({"C": 0, "1B": 1})
        assert result == ["1B"]


# ---------------------------------------------------------------------------
# build_team_slot_template
# ---------------------------------------------------------------------------

class TestBuildTeamSlotTemplate:
    def test_same_as_build_slot_list(self):
        per_team = {"C": 1, "SS": 1, "OF": 3}
        result = build_team_slot_template(per_team)
        expected = build_slot_list(per_team)
        assert sorted(result) == sorted(expected)


# ---------------------------------------------------------------------------
# validate_assigned_slots
# ---------------------------------------------------------------------------

class TestValidateAssignedSlots:
    def test_valid_assignment_passes(self):
        df = pd.DataFrame({
            "Player": ["A", "B"],
            "AssignedSlot": ["1B", "SS"],
            "_assign_idx": [0, 1],
        })
        elig_sets = [{"1B", "CI", "UT"}, {"SS", "MI", "UT"}]
        validate_assigned_slots(df, {"1B": 1, "SS": 1}, elig_sets, "test")

    def test_ineligible_raises(self):
        df = pd.DataFrame({
            "Player": ["A"],
            "AssignedSlot": ["C"],
            "_assign_idx": [0],
        })
        elig_sets = [{"1B", "UT"}]  # Not eligible for C
        with pytest.raises(ValueError, match="ineligible"):
            validate_assigned_slots(df, {"C": 1}, elig_sets, "test")

    def test_missing_slot_raises(self):
        df = pd.DataFrame({
            "Player": ["A"],
            "AssignedSlot": ["1B"],
            "_assign_idx": [0],
        })
        elig_sets = [{"1B", "CI", "UT"}]
        with pytest.raises(ValueError, match="cannot fill"):
            validate_assigned_slots(df, {"1B": 1, "SS": 1}, elig_sets, "test")

    def test_empty_assignment_and_zero_slots_ok(self):
        df = pd.DataFrame({"Player": [], "AssignedSlot": [], "_assign_idx": []})
        validate_assigned_slots(df, {}, [], "test")

    def test_missing_assign_idx_raises(self):
        df = pd.DataFrame({"Player": ["A"], "AssignedSlot": ["1B"]})
        with pytest.raises(ValueError, match="_assign_idx"):
            validate_assigned_slots(df, {"1B": 1}, [{"1B"}], "test")


# ---------------------------------------------------------------------------
# assign_players_to_slots
# ---------------------------------------------------------------------------

def _make_hitter_df(players):
    """Helper: [("Name", "Pos", weight), ...] → DataFrame."""
    rows = []
    for name, pos, weight in players:
        rows.append({
            "Player": name,
            "Pos": pos,
            "Year": 2026,
            "Team": "TST",
            "Age": 25,
            "weight": weight,
        })
    return pd.DataFrame(rows)


class TestAssignPlayersToSlots:
    def test_basic_hitter_assignment(self):
        df = _make_hitter_df([
            ("Alice", "1B", 10.0),
            ("Bob", "SS", 8.0),
            ("Carol", "OF", 6.0),
        ])
        slot_counts = {"1B": 1, "SS": 1, "OF": 1}
        result = assign_players_to_slots(df, slot_counts, eligible_hit_slots)
        assert len(result) == 3
        assert set(result["AssignedSlot"]) == {"1B", "SS", "OF"}

    def test_zero_slots_returns_empty(self):
        df = _make_hitter_df([("Alice", "1B", 10.0)])
        result = assign_players_to_slots(df, {}, eligible_hit_slots)
        assert len(result) == 0

    def test_insufficient_players_raises(self):
        df = _make_hitter_df([("Alice", "1B", 10.0)])
        with pytest.raises(ValueError, match="Not enough players"):
            assign_players_to_slots(df, {"1B": 1, "SS": 1}, eligible_hit_slots)

    def test_ineligible_slot_raises(self):
        df = _make_hitter_df([
            ("Alice", "1B", 10.0),
            ("Bob", "1B", 8.0),
        ])
        # Need a C but nobody plays C
        with pytest.raises(ValueError, match="Cannot fill slot"):
            assign_players_to_slots(df, {"C": 1, "1B": 1}, eligible_hit_slots)

    def test_multi_eligible_player_gets_best_slot(self):
        df = _make_hitter_df([
            ("Alice", "1B/3B", 10.0),
            ("Bob", "3B", 8.0),
            ("Carol", "1B", 6.0),
        ])
        slot_counts = {"1B": 1, "3B": 1, "UT": 1}
        result = assign_players_to_slots(df, slot_counts, eligible_hit_slots)
        assert len(result) == 3

    def test_pitcher_assignment(self):
        df = pd.DataFrame([
            {"Player": "P1", "Pos": "SP", "Year": 2026, "Team": "T", "Age": 25, "weight": 5.0},
            {"Player": "P2", "Pos": "RP", "Year": 2026, "Team": "T", "Age": 27, "weight": 3.0},
        ])
        slot_counts = {"SP": 1, "RP": 1}
        result = assign_players_to_slots(df, slot_counts, eligible_pit_slots)
        assert len(result) == 2
        assigned_slots = set(result["AssignedSlot"])
        assert assigned_slots == {"SP", "RP"}

    def test_higher_weight_preferred(self):
        df = _make_hitter_df([
            ("Alice", "1B", 20.0),
            ("Bob", "1B", 5.0),
            ("Carol", "OF", 3.0),
        ])
        slot_counts = {"1B": 1, "UT": 1}
        result = assign_players_to_slots(df, slot_counts, eligible_hit_slots)
        # Alice should be assigned — highest weight
        assert "Alice" in result["Player"].values
