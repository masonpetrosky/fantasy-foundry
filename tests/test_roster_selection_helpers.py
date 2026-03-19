import unittest

import pandas as pd
import pytest

from backend.dynasty_roto_values import _non_vacant_player_names, _select_mlb_roster_with_active_floor

pytestmark = pytest.mark.valuation


class RosterSelectionHelperTests(unittest.TestCase):
    def test_non_vacant_player_names_filters_placeholder_rows(self) -> None:
        assigned = pd.DataFrame(
            [
                {"Player": "Real Player"},
                {"Player": "__VACANT_HITTER_2026_C_1_1"},
                {"Player": "Another Player"},
                {"Player": None},
            ]
        )

        names = _non_vacant_player_names(assigned)
        self.assertEqual(names, {"Real Player", "Another Player"})

    def test_select_mlb_roster_with_active_floor_preserves_floor_player(self) -> None:
        stash_sorted = pd.DataFrame(
            [
                {"Player": "A", "StashScore": 10.0},
                {"Player": "B", "StashScore": 9.0},
                {"Player": "C", "StashScore": 8.0},
                {"Player": "D", "StashScore": 7.0},
                {"Player": "E", "StashScore": 6.0},
            ]
        )

        selected = _select_mlb_roster_with_active_floor(
            stash_sorted,
            excluded_players=set(),
            total_mlb_slots=3,
            active_floor_names={"D"},
        )

        self.assertEqual(len(selected), 3)
        self.assertIn("D", set(selected["Player"]))
        self.assertIn("A", set(selected["Player"]))
        self.assertIn("B", set(selected["Player"]))

    def test_select_mlb_roster_with_active_floor_respects_exclusions(self) -> None:
        stash_sorted = pd.DataFrame(
            [
                {"Player": "A", "StashScore": 10.0},
                {"Player": "B", "StashScore": 9.0},
                {"Player": "C", "StashScore": 8.0},
                {"Player": "D", "StashScore": 7.0},
            ]
        )

        selected = _select_mlb_roster_with_active_floor(
            stash_sorted,
            excluded_players={"B"},
            total_mlb_slots=2,
            active_floor_names={"B", "D"},
        )

        self.assertEqual(len(selected), 2)
        self.assertNotIn("B", set(selected["Player"]))
        self.assertIn("D", set(selected["Player"]))

    def test_select_mlb_roster_with_active_floor_prefers_mlb_playing_time_players(self) -> None:
        stash_sorted = pd.DataFrame(
            [
                {"Player": "Prospect A", "StashScore": 0.0},
                {"Player": "Prospect B", "StashScore": 0.0},
                {"Player": "Veteran A", "StashScore": -0.1},
                {"Player": "Veteran B", "StashScore": -0.2},
            ]
        )

        selected = _select_mlb_roster_with_active_floor(
            stash_sorted,
            excluded_players=set(),
            total_mlb_slots=2,
            active_floor_names=set(),
            mlb_playing_time_players={"Veteran A", "Veteran B"},
        )

        self.assertEqual(list(selected["Player"]), ["Veteran A", "Veteran B"])


if __name__ == "__main__":
    unittest.main()
