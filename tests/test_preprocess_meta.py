import unittest

import pandas as pd

import preprocess


class BuildMetaTests(unittest.TestCase):
    def test_build_meta_unions_years_from_both_sheets(self) -> None:
        bat = pd.DataFrame(
            {
                "Player": ["A", "B", "B"],
                "Team": ["NYY", "LAD", "lad"],
                "Year": [2026, "2027", None],
                "Pos": ["OF", "1B", "1B"],
            }
        )
        pit = pd.DataFrame(
            {
                "Player": ["C", "D"],
                "MLBTeam": ["SEA", "NYY"],
                "Year": [2025.0, "2028"],
                "Pos": ["SP", "RP"],
            }
        )

        meta = preprocess.build_meta(bat, pit)

        self.assertEqual(meta["years"], [2025, 2026, 2027, 2028])
        self.assertEqual(meta["teams"], ["LAD", "NYY", "SEA"])
        self.assertEqual(meta["bat_positions"], ["1B", "OF"])
        self.assertEqual(meta["pit_positions"], ["RP", "SP"])
        self.assertEqual(meta["total_hitters"], 2)
        self.assertEqual(meta["total_pitchers"], 2)

    def test_build_meta_handles_missing_optional_columns(self) -> None:
        bat = pd.DataFrame({"Player": ["A"], "Year": ["bad"]})
        pit = pd.DataFrame({"Other": [1, 2]})

        meta = preprocess.build_meta(bat, pit)

        self.assertEqual(meta["teams"], [])
        self.assertEqual(meta["years"], [])
        self.assertEqual(meta["bat_positions"], [])
        self.assertEqual(meta["pit_positions"], [])
        self.assertEqual(meta["total_hitters"], 1)
        self.assertEqual(meta["total_pitchers"], 0)

    def test_extract_years_ignores_fractional_values(self) -> None:
        df = pd.DataFrame({"Year": [2026.0, 2027.5, "2028", "bad", None]})
        years = preprocess._extract_years(df)
        self.assertEqual(years, {2026, 2028})


if __name__ == "__main__":
    unittest.main()
