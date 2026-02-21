import unittest
import warnings

import pandas as pd

from backend.dynasty_roto_values import (
    PIT_COMPONENT_COLS,
    CommonDynastyRotoSettings,
    _apply_negative_value_stash_rules,
    _bench_stash_round_penalty,
    _build_bench_stash_penalty_map,
    _estimate_bench_negative_penalty,
    _infer_minor_eligibility_by_year,
    _players_with_playing_time,
    assign_players_to_slots_with_vacancy_fill,
    compute_year_context,
    compute_year_player_values,
    eligible_pit_slots,
)


class VacancyBackfillTests(unittest.TestCase):
    def test_assign_players_to_slots_with_vacancy_fill_backfills_shortage(self) -> None:
        pit = pd.DataFrame(
            [
                {
                    "Player": "One Reliever",
                    "Year": 2026,
                    "Team": "AAA",
                    "Age": 28,
                    "Pos": "RP",
                    "IP": 60.0,
                    "W": 4.0,
                    "QS": 0.0,
                    "K": 70.0,
                    "SVH": 20.0,
                    "ER": 18.0,
                    "H": 45.0,
                    "BB": 16.0,
                    "ERA": 2.70,
                    "WHIP": 1.02,
                    "weight": 1.0,
                }
            ]
        )
        slot_counts = {"RP": 2}

        assigned = assign_players_to_slots_with_vacancy_fill(
            pit,
            slot_counts,
            eligible_pit_slots,
            stat_cols=PIT_COMPONENT_COLS,
            year=2026,
            side_label="pitcher",
            weight_col="weight",
        )

        self.assertEqual(len(assigned), 2)
        self.assertEqual(int((assigned["AssignedSlot"] == "RP").sum()), 2)

        vacancy_rows = assigned[assigned["Player"].astype(str).str.startswith("__VACANT_PITCHER_2026_RP_")]
        self.assertEqual(len(vacancy_rows), 1)
        self.assertEqual(float(vacancy_rows["IP"].iloc[0]), 0.0)
        self.assertEqual(float(vacancy_rows["SVH"].iloc[0]), 0.0)

    def test_compute_year_context_handles_slot_shortage_with_vacancy_backfill(self) -> None:
        bat = pd.DataFrame(
            [
                {
                    "Player": "Catcher One",
                    "Year": 2026,
                    "Team": "AAA",
                    "Age": 27,
                    "Pos": "C",
                    "AB": 500.0,
                    "H": 130.0,
                    "R": 60.0,
                    "HR": 18.0,
                    "RBI": 70.0,
                    "SB": 4.0,
                },
                {
                    "Player": "Catcher Two",
                    "Year": 2026,
                    "Team": "BBB",
                    "Age": 28,
                    "Pos": "C",
                    "AB": 480.0,
                    "H": 120.0,
                    "R": 58.0,
                    "HR": 16.0,
                    "RBI": 65.0,
                    "SB": 3.0,
                },
            ]
        )
        pit = pd.DataFrame(
            [
                {
                    "Player": "Only RP",
                    "Year": 2026,
                    "Team": "AAA",
                    "Age": 29,
                    "Pos": "RP",
                    "IP": 60.0,
                    "W": 4.0,
                    "QS": 0.0,
                    "K": 70.0,
                    "SVH": 20.0,
                    "ER": 18.0,
                    "H": 45.0,
                    "BB": 16.0,
                    "ERA": 2.70,
                    "WHIP": 1.02,
                }
            ]
        )

        lg = CommonDynastyRotoSettings(
            n_teams=2,
            sims_for_sgp=2,
            hitter_slots={"C": 1, "1B": 0, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 0, "UT": 0},
            pitcher_slots={"P": 0, "SP": 0, "RP": 2},
            bench_slots=0,
            minor_slots=0,
            ir_slots=0,
            ip_min=0.0,
            ip_max=None,
        )

        ctx = compute_year_context(2026, bat, pit, lg, rng_seed=7)

        self.assertIn("RP", ctx["baseline_pit"].index)
        self.assertAlmostEqual(float(ctx["base_pit_tot"]["IP"]), 30.0, places=6)

    def test_compute_year_player_values_handles_hitter_columns_with_digits(self) -> None:
        bat = pd.DataFrame(
            [
                {
                    "Player": "Corner Bat",
                    "Year": 2026,
                    "Team": "AAA",
                    "Age": 27,
                    "Pos": "3B",
                    "AB": 550.0,
                    "H": 150.0,
                    "R": 85.0,
                    "HR": 28.0,
                    "RBI": 92.0,
                    "SB": 5.0,
                    "BB": 62.0,
                    "HBP": 4.0,
                    "SF": 5.0,
                    "2B": 32.0,
                    "3B": 2.0,
                },
                {
                    "Player": "Middle Bat",
                    "Year": 2026,
                    "Team": "BBB",
                    "Age": 25,
                    "Pos": "SS",
                    "AB": 520.0,
                    "H": 142.0,
                    "R": 80.0,
                    "HR": 22.0,
                    "RBI": 78.0,
                    "SB": 12.0,
                    "BB": 58.0,
                    "HBP": 6.0,
                    "SF": 4.0,
                    "2B": 27.0,
                    "3B": 3.0,
                },
            ]
        )
        pit = pd.DataFrame(
            [
                {
                    "Player": "Starter One",
                    "Year": 2026,
                    "Team": "AAA",
                    "Age": 28,
                    "Pos": "SP",
                    "IP": 170.0,
                    "W": 12.0,
                    "QS": 18.0,
                    "K": 180.0,
                    "SVH": 0.0,
                    "ER": 64.0,
                    "H": 152.0,
                    "BB": 48.0,
                    "ERA": 3.39,
                    "WHIP": 1.18,
                },
                {
                    "Player": "Reliever One",
                    "Year": 2026,
                    "Team": "BBB",
                    "Age": 29,
                    "Pos": "RP",
                    "IP": 64.0,
                    "W": 4.0,
                    "QS": 0.0,
                    "K": 82.0,
                    "SVH": 28.0,
                    "ER": 18.0,
                    "H": 50.0,
                    "BB": 20.0,
                    "ERA": 2.53,
                    "WHIP": 1.09,
                },
            ]
        )

        lg = CommonDynastyRotoSettings(
            n_teams=1,
            sims_for_sgp=2,
            hitter_slots={"C": 0, "1B": 0, "2B": 0, "3B": 1, "SS": 1, "CI": 0, "MI": 0, "OF": 0, "UT": 0},
            pitcher_slots={"P": 0, "SP": 1, "RP": 1},
            bench_slots=0,
            minor_slots=0,
            ir_slots=0,
            ip_min=0.0,
            ip_max=None,
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ctx = compute_year_context(2026, bat, pit, lg, rng_seed=13)
        hit_vals, pit_vals = compute_year_player_values(ctx, lg)
        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        self.assertEqual(runtime_warnings, [])

        self.assertEqual(set(hit_vals["Player"]), {"Corner Bat", "Middle Bat"})
        self.assertEqual(set(pit_vals["Player"]), {"Starter One", "Reliever One"})


class BenchStashPenaltyTests(unittest.TestCase):
    def test_players_with_playing_time_includes_pitchers_and_filters_zero_playing_time(self) -> None:
        bat = pd.DataFrame(
            [
                {"Player": "Hitter", "Year": 2026, "AB": 200.0},
                {"Player": "NoBat", "Year": 2026, "AB": 0.0},
            ]
        )
        pit = pd.DataFrame(
            [
                {"Player": "Pitcher", "Year": 2026, "IP": 55.0},
                {"Player": "NoIP", "Year": 2026, "IP": 0.0},
                {"Player": "FuturePitcher", "Year": 2027, "IP": 40.0},
            ]
        )

        players = _players_with_playing_time(bat, pit, [2026])

        self.assertEqual(players, {"Hitter", "Pitcher"})

    def test_estimate_bench_negative_penalty_uses_open_hitter_games(self) -> None:
        lg_two_bench = CommonDynastyRotoSettings(
            n_teams=1,
            hitter_slots={"C": 1, "1B": 1, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 0, "UT": 0},
            pitcher_slots={"P": 0, "SP": 0, "RP": 0},
            bench_slots=2,
            minor_slots=0,
            ir_slots=0,
        )
        assigned_hit = pd.DataFrame(
            [
                {"Player": "Starter One", "G": 162.0},
                {"Player": "Starter Two", "G": 81.0},
            ]
        )
        penalty = _estimate_bench_negative_penalty({"assigned_hit": assigned_hit}, lg_two_bench)
        self.assertAlmostEqual(penalty, 0.0, places=6)

        lg_one_bench = CommonDynastyRotoSettings(
            n_teams=1,
            hitter_slots={"C": 1, "1B": 1, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 0, "UT": 0},
            pitcher_slots={"P": 0, "SP": 0, "RP": 0},
            bench_slots=1,
            minor_slots=0,
            ir_slots=0,
        )
        penalty_one_bench = _estimate_bench_negative_penalty({"assigned_hit": assigned_hit}, lg_one_bench)
        self.assertAlmostEqual(penalty_one_bench, 0.5, places=6)

    def test_apply_negative_value_stash_rules_prioritizes_minor_then_bench(self) -> None:
        self.assertEqual(
            _apply_negative_value_stash_rules(
                -4.0,
                can_minor_stash=True,
                can_bench_stash=True,
                bench_negative_penalty=0.3,
            ),
            0.0,
        )
        self.assertAlmostEqual(
            _apply_negative_value_stash_rules(
                -4.0,
                can_minor_stash=False,
                can_bench_stash=True,
                bench_negative_penalty=0.3,
            ),
            -1.2,
            places=6,
        )
        self.assertEqual(
            _apply_negative_value_stash_rules(
                2.0,
                can_minor_stash=True,
                can_bench_stash=True,
                bench_negative_penalty=0.3,
            ),
            2.0,
        )

    def test_bench_stash_round_penalty_grows_and_caps(self) -> None:
        round_one = _bench_stash_round_penalty(1, bench_slots=6)
        round_three = _bench_stash_round_penalty(3, bench_slots=6)
        round_six = _bench_stash_round_penalty(6, bench_slots=6)
        round_seven = _bench_stash_round_penalty(7, bench_slots=6)

        self.assertGreater(round_one, 0.0)
        self.assertLess(round_one, round_three)
        self.assertLess(round_three, round_six)
        self.assertLess(round_six, 1.0)
        self.assertEqual(round_seven, 1.0)

    def test_build_bench_stash_penalty_map_groups_players_into_team_rounds(self) -> None:
        stash_sorted = pd.DataFrame(
            [
                {"Player": "A", "StashScore": 10.0},
                {"Player": "B", "StashScore": 9.0},
                {"Player": "C", "StashScore": 8.0},
                {"Player": "D", "StashScore": 7.0},
                {"Player": "E", "StashScore": 6.0},
                {"Player": "F", "StashScore": 5.0},
                {"Player": "G", "StashScore": 4.0},
            ]
        )
        penalties = _build_bench_stash_penalty_map(
            stash_sorted,
            bench_stash_players={"A", "B", "C", "D", "E", "F", "G"},
            n_teams=2,
            bench_slots=3,
        )

        self.assertAlmostEqual(penalties["A"], penalties["B"], places=9)
        self.assertAlmostEqual(penalties["C"], penalties["D"], places=9)
        self.assertAlmostEqual(penalties["E"], penalties["F"], places=9)
        self.assertLess(penalties["A"], penalties["C"])
        self.assertLess(penalties["C"], penalties["E"])
        self.assertEqual(penalties["G"], 1.0)

    def test_infer_minor_eligibility_by_year_drops_after_cumulative_usage_crosses_limit(self) -> None:
        bat = pd.DataFrame(
            [
                {"Player": "Prospect", "Year": 2026, "AB": 60.0, "Age": 22.0},
                {"Player": "Prospect", "Year": 2027, "AB": 80.0, "Age": 23.0},
                {"Player": "Prospect", "Year": 2028, "AB": 20.0, "Age": 24.0},
                {"Player": "Steady", "Year": 2026, "AB": 30.0, "Age": 21.0},
                {"Player": "Steady", "Year": 2027, "AB": 30.0, "Age": 22.0},
            ]
        )
        pit = pd.DataFrame(columns=["Player", "Year", "IP", "Age"])

        inferred = _infer_minor_eligibility_by_year(
            bat,
            pit,
            years=[2026, 2027, 2028],
            hitter_usage_max=130,
            pitcher_usage_max=50,
            hitter_age_max=25,
            pitcher_age_max=26,
        )
        by_key = {(row.Player, int(row.Year)): bool(row.minor_eligible) for row in inferred.itertuples(index=False)}

        self.assertTrue(by_key[("Prospect", 2026)])
        self.assertFalse(by_key[("Prospect", 2027)])
        self.assertFalse(by_key[("Prospect", 2028)])
        self.assertTrue(by_key[("Steady", 2026)])
        self.assertTrue(by_key[("Steady", 2027)])


if __name__ == "__main__":
    unittest.main()
