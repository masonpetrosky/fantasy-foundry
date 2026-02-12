import unittest

import pandas as pd

from backend.dynasty_roto_values import _non_vacant_player_names, _select_mlb_roster_with_active_floor


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


if __name__ == "__main__":
    unittest.main()
