import unittest

import backend.app as app_module


def _hitter_projection(
    *,
    team: str,
    date: str,
    ab: float,
    h: float,
    hr: float = 20.0,
    b2: float = 20.0,
    b3: float = 2.0,
    bb: float = 40.0,
    hbp: float = 3.0,
    sf: float = 4.0,
) -> dict:
    return {
        "Player": "Same Name",
        "Year": 2026,
        "Team": team,
        "Pos": "1B",
        "Date": date,
        "AB": ab,
        "H": h,
        "2B": b2,
        "3B": b3,
        "HR": hr,
        "BB": bb,
        "HBP": hbp,
        "SF": sf,
    }


class AverageRecentProjectionRowsTests(unittest.TestCase):
    def test_disambiguates_same_name_and_year_by_team(self) -> None:
        records = [
            _hitter_projection(team="NYY", date="2026-02-08", ab=400.0, h=100.0),
            _hitter_projection(team="NYY", date="2026-02-08", ab=420.0, h=110.0),
            _hitter_projection(team="LAD", date="2026-02-10", ab=500.0, h=140.0),
        ]

        out = app_module._average_recent_projection_rows(records, is_hitter=True)

        self.assertEqual(len(out), 2)
        by_team = {row["Team"]: row for row in out}
        self.assertSetEqual(set(by_team), {"NYY", "LAD"})
        self.assertAlmostEqual(by_team["NYY"]["AB"], 410.0)
        self.assertAlmostEqual(by_team["LAD"]["AB"], 500.0)

    def test_same_team_rows_still_average_together(self) -> None:
        records = [
            _hitter_projection(team="NYY", date="2026-01-20", ab=380.0, h=90.0),
            _hitter_projection(team="NYY", date="2026-02-05", ab=410.0, h=105.0),
            _hitter_projection(team="NYY", date="2026-02-12", ab=430.0, h=115.0),
        ]

        out = app_module._average_recent_projection_rows(records, is_hitter=True)

        self.assertEqual(len(out), 1)
        row = out[0]
        self.assertEqual(row["Team"], "NYY")
        self.assertAlmostEqual(row["AB"], 430.0)
        self.assertNotIn("_entity_team", row)


if __name__ == "__main__":
    unittest.main()
