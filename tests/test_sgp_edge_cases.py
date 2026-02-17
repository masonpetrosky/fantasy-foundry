import math
import unittest
import warnings

import pandas as pd

from backend.dynasty_roto_values import (
    HAVE_SCIPY,
    CommonDynastyRotoSettings,
    LeagueSettings,
    compute_year_context,
    compute_year_player_values,
    league_compute_year_context,
    league_compute_year_player_values,
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
        self.assertEqual(set(ctx["sgp_pit"].keys()), {"W", "K", "SV", "ERA", "WHIP", "QS", "SVH"})
        self.assertTrue(all(float(value) == 0.0 for value in ctx["sgp_hit"].values()))
        self.assertTrue(all(float(value) == 0.0 for value in ctx["sgp_pit"].values()))

        hit_vals, pit_vals = compute_year_player_values(ctx, lg)
        self.assertEqual(len(hit_vals), 1)
        self.assertEqual(len(pit_vals), 1)
        self.assertTrue(math.isfinite(float(hit_vals["YearValue"].iloc[0])))
        self.assertTrue(math.isfinite(float(pit_vals["YearValue"].iloc[0])))

    @unittest.skipUnless(HAVE_SCIPY, "scipy is required for league assignment tests")
    def test_league_single_team_zero_sims_returns_zero_denominators(self) -> None:
        bat = pd.DataFrame(
            [
                {
                    "Player": "League Bat",
                    "Year": 2026,
                    "MLBTeam": "AAA",
                    "Age": 26,
                    "Pos": "OF",
                    "AB": 525.0,
                    "H": 148.0,
                    "R": 84.0,
                    "HR": 24.0,
                    "RBI": 82.0,
                    "SB": 10.0,
                    "BB": 58.0,
                    "HBP": 5.0,
                    "SF": 5.0,
                    "2B": 31.0,
                    "3B": 3.0,
                }
            ]
        )
        pit = pd.DataFrame(
            [
                {
                    "Player": "League Arm",
                    "Year": 2026,
                    "MLBTeam": "AAA",
                    "Age": 29,
                    "Pos": "SP",
                    "IP": 165.0,
                    "W": 11.0,
                    "K": 176.0,
                    "SVH": 0.0,
                    "QA3": 17.0,
                    "ER": 62.0,
                    "H": 150.0,
                    "BB": 47.0,
                    "ERA": 3.38,
                    "WHIP": 1.19,
                }
            ]
        )
        lg = LeagueSettings(
            n_teams=1,
            sims_for_sgp=0,
            hitter_slots={"C": 0, "1B": 0, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 0, "UT": 1},
            pitcher_slots={"SP": 0, "RP": 0, "P": 1},
            ip_min=0.0,
            ip_max=200.0,
            bench_slots=0,
            minor_slots=0,
            ir_slots=0,
        )

        ctx = league_compute_year_context(2026, bat, pit, lg, rng_seed=41)
        self.assertEqual(set(ctx["sgp_hit"].keys()), {"R", "HR", "RBI", "SB", "AVG", "OPS"})
        self.assertEqual(set(ctx["sgp_pit"].keys()), {"W", "K", "SVH", "QA3", "ERA", "WHIP"})
        self.assertTrue(all(float(value) == 0.0 for value in ctx["sgp_hit"].values()))
        self.assertTrue(all(float(value) == 0.0 for value in ctx["sgp_pit"].values()))

        hit_vals, pit_vals = league_compute_year_player_values(ctx, lg)
        self.assertEqual(len(hit_vals), 1)
        self.assertEqual(len(pit_vals), 1)
        self.assertTrue(math.isfinite(float(hit_vals["YearValue"].iloc[0])))
        self.assertTrue(math.isfinite(float(pit_vals["YearValue"].iloc[0])))

    @unittest.skipUnless(HAVE_SCIPY, "scipy is required for league assignment tests")
    def test_league_context_raises_clear_error_when_slot_has_no_eligible_players(self) -> None:
        bat = pd.DataFrame(
            [
                {
                    "Player": "No Catcher Eligible",
                    "Year": 2026,
                    "MLBTeam": "AAA",
                    "Age": 24,
                    "Pos": "OF",
                    "AB": 480.0,
                    "H": 132.0,
                    "R": 68.0,
                    "HR": 19.0,
                    "RBI": 71.0,
                    "SB": 14.0,
                    "BB": 44.0,
                    "HBP": 2.0,
                    "SF": 3.0,
                    "2B": 28.0,
                    "3B": 5.0,
                }
            ]
        )
        pit = pd.DataFrame(
            [
                {
                    "Player": "Eligible Pitcher",
                    "Year": 2026,
                    "MLBTeam": "AAA",
                    "Age": 28,
                    "Pos": "SP",
                    "IP": 140.0,
                    "W": 9.0,
                    "K": 150.0,
                    "SVH": 0.0,
                    "QA3": 15.0,
                    "ER": 55.0,
                    "H": 132.0,
                    "BB": 38.0,
                    "ERA": 3.54,
                    "WHIP": 1.21,
                }
            ]
        )
        lg = LeagueSettings(
            n_teams=1,
            sims_for_sgp=0,
            hitter_slots={"C": 1, "1B": 0, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 0, "UT": 0},
            pitcher_slots={"SP": 0, "RP": 0, "P": 1},
            ip_min=0.0,
            ip_max=200.0,
            bench_slots=0,
            minor_slots=0,
            ir_slots=0,
        )

        with self.assertRaisesRegex(ValueError, "Cannot fill slot 'C'"):
            league_compute_year_context(2026, bat, pit, lg, rng_seed=51)


if __name__ == "__main__":
    unittest.main()
