import unittest

import pandas as pd

import preprocess


class BuildMetaTests(unittest.TestCase):
    @staticmethod
    def _bat_frame(years: list[int]) -> pd.DataFrame:
        rows = []
        for year in years:
            rows.append(
                {
                    "Player": "Hitter A",
                    "Team": "NYY",
                    "Age": 27,
                    "Year": year,
                    "AB": 550,
                    "R": 90,
                    "RBI": 95,
                    "H": 165,
                    "2B": 30,
                    "3B": 2,
                    "HR": 28,
                    "BB": 60,
                    "IBB": 2,
                    "HBP": 4,
                    "SO": 120,
                    "SB": 10,
                    "CS": 3,
                    "SF": 5,
                    "SH": 0,
                    "GDP": 12,
                    "AVG": 0.300,
                    "OPS": 0.860,
                    "Pos": "OF",
                    "Date": "2026-01-01",
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _pitch_frame(years: list[int]) -> pd.DataFrame:
        rows = []
        for year in years:
            rows.append(
                {
                    "Player": "Pitcher A",
                    "Team": "SEA",
                    "Age": 28,
                    "Year": year,
                    "G": 32,
                    "GS": 32,
                    "IP": 180.0,
                    "BF": 740,
                    "W": 14,
                    "L": 8,
                    "SV": 0,
                    "HLD": 0,
                    "BS": 0,
                    "QS": 18,
                    "QA3": 22,
                    "K": 210,
                    "BB": 55,
                    "IBB": 1,
                    "HBP": 3,
                    "H": 150,
                    "HR": 20,
                    "R": 70,
                    "ER": 62,
                    "SVH": 0,
                    "ERA": 3.10,
                    "WHIP": 1.14,
                    "Pos": "SP",
                    "Date": "2026-01-01",
                }
            )
        return pd.DataFrame(rows)

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

    def test_add_player_keys_adds_stable_identity_columns(self) -> None:
        bat = pd.DataFrame(
            {
                "Player": ["Jane Roe"],
                "Team": ["SEA"],
                "Year": [2026],
            }
        )
        pit = pd.DataFrame(columns=["Player", "Team", "Year"])

        bat_out, pit_out = preprocess.add_player_keys(bat, pit)

        self.assertIn("PlayerKey", bat_out.columns)
        self.assertIn("PlayerEntityKey", bat_out.columns)
        self.assertEqual(bat_out.iloc[0]["PlayerKey"], "jane-roe")
        self.assertEqual(bat_out.iloc[0]["PlayerEntityKey"], "jane-roe")
        self.assertIn("PlayerKey", pit_out.columns)
        self.assertIn("PlayerEntityKey", pit_out.columns)

    def test_add_player_keys_disambiguates_same_name_by_team(self) -> None:
        bat = pd.DataFrame(
            {
                "Player": ["John Doe"],
                "Team": ["NYY"],
                "Year": [2026],
            }
        )
        pit = pd.DataFrame(
            {
                "Player": ["John Doe"],
                "Team": ["BOS"],
                "Year": [2026],
            }
        )

        bat_out, pit_out = preprocess.add_player_keys(bat, pit)
        self.assertEqual(bat_out.iloc[0]["PlayerKey"], "john-doe")
        self.assertEqual(pit_out.iloc[0]["PlayerKey"], "john-doe")
        self.assertEqual(bat_out.iloc[0]["PlayerEntityKey"], "john-doe__nyy")
        self.assertEqual(pit_out.iloc[0]["PlayerEntityKey"], "john-doe__bos")

    def test_validate_projection_workbook_frames_accepts_expected_schema(self) -> None:
        bat = self._bat_frame([2026, 2027])
        pit = self._pitch_frame([2026, 2027])

        report = preprocess.validate_projection_workbook_frames(bat, pit, min_year=2026, max_year=2027)

        self.assertTrue(report["year_sets_match"])
        self.assertEqual(report["validation_window"]["expected_years"], [2026, 2027])
        self.assertEqual(report["bat"]["invalid_year_values"], 0)
        self.assertEqual(report["pitch"]["invalid_year_values"], 0)

    def test_validate_projection_workbook_frames_rejects_missing_columns(self) -> None:
        bat = self._bat_frame([2026, 2027]).drop(columns=["Team"])
        pit = self._pitch_frame([2026, 2027])

        with self.assertRaisesRegex(ValueError, "Bat sheet is missing required columns: Team"):
            preprocess.validate_projection_workbook_frames(bat, pit, min_year=2026, max_year=2027)

    def test_validate_projection_workbook_frames_rejects_missing_years(self) -> None:
        bat = self._bat_frame([2026])
        pit = self._pitch_frame([2026, 2027])

        with self.assertRaisesRegex(ValueError, "Bat sheet is missing projection years: 2027"):
            preprocess.validate_projection_workbook_frames(bat, pit, min_year=2026, max_year=2027)

    def test_validate_projection_workbook_frames_rejects_non_integer_year_values(self) -> None:
        bat = self._bat_frame([2026, 2027])
        pit = self._pitch_frame([2026, 2027])
        bat["Year"] = bat["Year"].astype("float64")
        bat.loc[1, "Year"] = 2026.5

        with self.assertRaisesRegex(ValueError, "Bat sheet contains 1 row\\(s\\) with non-integer Year values"):
            preprocess.validate_projection_workbook_frames(bat, pit, min_year=2026, max_year=2027)


if __name__ == "__main__":
    unittest.main()
