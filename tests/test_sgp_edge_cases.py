import math
import unittest
import warnings

import pandas as pd

from backend.dynasty_roto_values import (
    CommonDynastyRotoSettings,
    compute_year_context,
    compute_year_player_values,
)


class SGPEdgeCaseTests(unittest.TestCase):
    def test_common_single_team_zero_sims_returns_zero_denominators_without_runtime_warnings(self) -> None:
        bat = pd.DataFrame(
            [
                {
                    "Player": "Single Team Bat",
                    "Year": 2026,
                    "Team": "AAA",
                    "Age": 27,
                    "Pos": "1B",
                    "AB": 510.0,
                    "H": 145.0,
                    "R": 78.0,
                    "HR": 25.0,
                    "RBI": 89.0,
                    "SB": 6.0,
                    "BB": 55.0,
                    "HBP": 3.0,
                    "SF": 4.0,
                    "2B": 30.0,
                    "3B": 2.0,
                }
            ]
        )
        pit = pd.DataFrame(
            [
                {
                    "Player": "Single Team Arm",
                    "Year": 2026,
                    "Team": "AAA",
                    "Age": 28,
                    "Pos": "SP",
                    "IP": 175.0,
                    "W": 12.0,
                    "QS": 19.0,
                    "K": 188.0,
                    "SV": 0.0,
                    "SVH": 0.0,
                    "ER": 66.0,
                    "H": 154.0,
                    "BB": 50.0,
                    "ERA": 3.39,
                    "WHIP": 1.17,
                }
            ]
        )
        lg = CommonDynastyRotoSettings(
            n_teams=1,
            sims_for_sgp=0,
            hitter_slots={"C": 0, "1B": 0, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 0, "UT": 1},
            pitcher_slots={"P": 1, "SP": 0, "RP": 0},
            bench_slots=0,
            minor_slots=0,
            ir_slots=0,
            ip_min=0.0,
            ip_max=None,
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ctx = compute_year_context(2026, bat, pit, lg, rng_seed=31)
        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        self.assertEqual(runtime_warnings, [])

        self.assertEqual(set(ctx["sgp_hit"].keys()), {"R", "RBI", "HR", "SB", "AVG", "OBP", "SLG", "OPS", "H", "BB", "2B", "TB"})
        self.assertEqual(set(ctx["sgp_pit"].keys()), {"W", "K", "SV", "ERA", "WHIP", "QS", "QA3", "SVH"})
        self.assertTrue(all(float(value) == 0.0 for value in ctx["sgp_hit"].values()))
        self.assertTrue(all(float(value) == 0.0 for value in ctx["sgp_pit"].values()))

        hit_vals, pit_vals = compute_year_player_values(ctx, lg)
        self.assertEqual(len(hit_vals), 1)
        self.assertEqual(len(pit_vals), 1)
        self.assertTrue(math.isfinite(float(hit_vals["YearValue"].iloc[0])))
        self.assertTrue(math.isfinite(float(pit_vals["YearValue"].iloc[0])))

if __name__ == "__main__":
    unittest.main()
