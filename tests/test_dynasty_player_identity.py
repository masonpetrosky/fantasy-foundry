import unittest

import pandas as pd

from backend.dynasty_roto_values import (
    _add_player_identity_keys,
    _attach_identity_columns_to_output,
    _build_player_identity_lookup,
    average_recent_projections,
)


class DynastyIdentityTests(unittest.TestCase):
    def test_average_recent_projections_disambiguates_same_name_by_team(self) -> None:
        df = pd.DataFrame(
            [
                {"Player": "Same Name", "Year": 2026, "Team": "NYY", "Date": "2026-02-01", "AB": 400.0, "H": 100.0},
                {"Player": "Same Name", "Year": 2026, "Team": "NYY", "Date": "2026-02-08", "AB": 420.0, "H": 110.0},
                {"Player": "Same Name", "Year": 2026, "Team": "LAD", "Date": "2026-02-10", "AB": 500.0, "H": 140.0},
            ]
        )

        out = average_recent_projections(df, stat_cols=["AB", "H"], max_entries=3)

        self.assertEqual(len(out), 2)
        by_team = {str(row["Team"]): row for _, row in out.iterrows()}
        self.assertSetEqual(set(by_team), {"NYY", "LAD"})
        self.assertEqual(int(by_team["NYY"]["ProjectionsUsed"]), 2)
        self.assertAlmostEqual(float(by_team["NYY"]["AB"]), 410.0, places=6)
        self.assertEqual(int(by_team["LAD"]["ProjectionsUsed"]), 1)
        self.assertAlmostEqual(float(by_team["LAD"]["AB"]), 500.0, places=6)

    def test_add_player_identity_keys_disambiguates_same_name_by_team(self) -> None:
        bat = pd.DataFrame(
            [
                {"Player": "Max Muncy", "Year": 2026, "Team": "Athletics"},
                {"Player": "Max Muncy", "Year": 2026, "Team": "Dodgers"},
            ]
        )
        pit = pd.DataFrame(columns=["Player", "Year", "Team"])

        bat_out, _pit_out = _add_player_identity_keys(bat, pit)
        entities = set(bat_out["PlayerEntityKey"].astype(str))
        self.assertSetEqual(entities, {"max-muncy__athletics", "max-muncy__dodgers"})

    def test_attach_identity_columns_restores_display_names(self) -> None:
        bat = pd.DataFrame(
            [
                {"Player": "Max Muncy", "Year": 2026, "Team": "Athletics"},
                {"Player": "Max Muncy", "Year": 2026, "Team": "Dodgers"},
            ]
        )
        pit = pd.DataFrame(columns=["Player", "Year", "Team"])
        bat_out, pit_out = _add_player_identity_keys(bat, pit)
        lookup = _build_player_identity_lookup(bat_out, pit_out)

        out = pd.DataFrame(
            [
                {"Player": "max-muncy__athletics", "DynastyValue": 1.2},
                {"Player": "max-muncy__dodgers", "DynastyValue": -0.7},
            ]
        )
        restored = _attach_identity_columns_to_output(out, lookup)

        self.assertListEqual(
            list(restored.columns[:3]),
            ["Player", "PlayerKey", "PlayerEntityKey"],
        )
        self.assertTrue((restored["Player"] == "Max Muncy").all())


if __name__ == "__main__":
    unittest.main()
