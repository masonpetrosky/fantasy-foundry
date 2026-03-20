import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

import backend.app as app_module


class DynastyValuePenaltyRemovalTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module._calculate_common_dynasty_frame_cached.cache_clear()
        app_module._calculate_points_dynasty_frame_cached.cache_clear()

    def test_common_cache_frame_keeps_calculated_values_without_post_scaling(self) -> None:
        fake_out = pd.DataFrame(
            [
                {
                    "Player": "Prospect One",
                    "Team": "ATL",
                    "Pos": "OF",
                    "Age": 22,
                    "DynastyValue": 12.5,
                    "RawDynastyValue": 14.0,
                    "minor_eligible": True,
                    "Value_2026": 8.0,
                }
            ]
        )

        class FakeSettings:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        def fake_calculate(*args, **kwargs):
            return fake_out.copy(deep=True)

        fake_module = types.SimpleNamespace(
            CommonDynastyRotoSettings=FakeSettings,
            calculate_common_dynasty_values=fake_calculate,
        )

        with patch.dict(sys.modules, {"dynasty_roto_values": fake_module}):
            out = app_module._calculate_common_dynasty_frame_cached(
                teams=12,
                sims=300,
                horizon=1,
                discount=0.94,
                hit_c=1,
                hit_1b=1,
                hit_2b=1,
                hit_3b=1,
                hit_ss=1,
                hit_ci=1,
                hit_mi=1,
                hit_of=5,
                hit_ut=1,
                pit_p=9,
                pit_sp=0,
                pit_rp=0,
                bench=6,
                minors=0,
                ir=0,
                ip_min=1000.0,
                ip_max=None,
                two_way="sum",
                start_year=2026,
            )

        row = out.iloc[0]
        self.assertEqual(float(row["DynastyValue"]), 12.5)
        self.assertEqual(float(row["RawDynastyValue"]), 14.0)
        self.assertEqual(float(row["Value_2026"]), 8.0)

    def test_points_cache_frame_uses_raw_replacement_math_without_confidence_penalty(self) -> None:
        bat_rows = [
            {
                "Player": "Hitter A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 22,
                "AB": 50,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "hitter-a",
                "PlayerEntityKey": "hitter-a",
            },
            {
                "Player": "Hitter B",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 30,
                "AB": 50,
                "H": 4,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "hitter-b",
                "PlayerEntityKey": "hitter-b",
            },
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(app_module, "PIT_DATA", []), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ):
            out = app_module._calculate_points_dynasty_frame_cached(
                teams=1,
                horizon=1,
                discount=1.0,
                hit_c=0,
                hit_1b=0,
                hit_2b=0,
                hit_3b=0,
                hit_ss=0,
                hit_ci=0,
                hit_mi=0,
                hit_of=1,
                hit_ut=0,
                pit_p=0,
                pit_sp=0,
                pit_rp=0,
                bench=1,
                minors=0,
                ir=0,
                keeper_limit=None,
                two_way="sum",
                points_valuation_mode="season_total",
                weekly_starts_cap=None,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=None,
                start_year=2026,
                pts_hit_1b=1.0,
                pts_hit_2b=0.0,
                pts_hit_3b=0.0,
                pts_hit_hr=0.0,
                pts_hit_r=0.0,
                pts_hit_rbi=0.0,
                pts_hit_sb=0.0,
                pts_hit_bb=0.0,
                pts_hit_hbp=0.0,
                pts_hit_so=0.0,
                pts_pit_ip=0.0,
                pts_pit_w=0.0,
                pts_pit_l=0.0,
                pts_pit_k=0.0,
                pts_pit_sv=0.0,
                pts_pit_hld=0.0,
                pts_pit_h=0.0,
                pts_pit_er=0.0,
                pts_pit_bb=0.0,
                pts_pit_hbp=0.0,
            )

        rows_by_player = {str(row["Player"]): row for _, row in out.iterrows()}
        self.assertEqual(float(rows_by_player["Hitter A"]["Value_2026"]), 10.0)
        self.assertEqual(float(rows_by_player["Hitter A"]["RawDynastyValue"]), 10.0)
        self.assertEqual(float(rows_by_player["Hitter A"]["DynastyValue"]), 10.0)
        self.assertEqual(float(rows_by_player["Hitter B"]["Value_2026"]), 0.0)
        self.assertEqual(float(rows_by_player["Hitter B"]["RawDynastyValue"]), 0.0)
        self.assertEqual(float(rows_by_player["Hitter B"]["DynastyValue"]), 0.0)

    def test_points_depth_uses_in_season_roster_size_unless_keeper_limit_is_set(self) -> None:
        bat_rows = [
            {
                "Player": "Hitter A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 24,
                "AB": 50,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "hitter-a",
                "PlayerEntityKey": "hitter-a",
            },
            {
                "Player": "Hitter B",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 25,
                "AB": 50,
                "H": 8,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "hitter-b",
                "PlayerEntityKey": "hitter-b",
            },
            {
                "Player": "Hitter C",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 26,
                "AB": 50,
                "H": 6,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "hitter-c",
                "PlayerEntityKey": "hitter-c",
            },
        ]

        calc_kwargs = {
            "teams": 1,
            "horizon": 1,
            "discount": 1.0,
            "hit_c": 0,
            "hit_1b": 0,
            "hit_2b": 0,
            "hit_3b": 0,
            "hit_ss": 0,
            "hit_ci": 0,
            "hit_mi": 0,
            "hit_of": 1,
            "hit_ut": 0,
            "pit_p": 0,
            "pit_sp": 0,
            "pit_rp": 0,
            "keeper_limit": None,
            "two_way": "sum",
            "points_valuation_mode": "season_total",
            "weekly_starts_cap": None,
            "allow_same_day_starts_overflow": False,
            "weekly_acquisition_cap": None,
            "start_year": 2026,
            "pts_hit_1b": 1.0,
            "pts_hit_2b": 0.0,
            "pts_hit_3b": 0.0,
            "pts_hit_hr": 0.0,
            "pts_hit_r": 0.0,
            "pts_hit_rbi": 0.0,
            "pts_hit_sb": 0.0,
            "pts_hit_bb": 0.0,
            "pts_hit_hbp": 0.0,
            "pts_hit_so": 0.0,
            "pts_pit_ip": 0.0,
            "pts_pit_w": 0.0,
            "pts_pit_l": 0.0,
            "pts_pit_k": 0.0,
            "pts_pit_sv": 0.0,
            "pts_pit_hld": 0.0,
            "pts_pit_h": 0.0,
            "pts_pit_er": 0.0,
            "pts_pit_bb": 0.0,
            "pts_pit_hbp": 0.0,
        }

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(app_module, "PIT_DATA", []), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ):
            shallow = app_module._calculate_points_dynasty_frame_cached(
                **calc_kwargs,
                bench=0,
                minors=0,
                ir=0,
            )
            deep = app_module._calculate_points_dynasty_frame_cached(
                **calc_kwargs,
                bench=8,
                minors=12,
                ir=6,
            )
            keeper_limited_kwargs = {**calc_kwargs, "keeper_limit": 1}
            keeper_limited = app_module._calculate_points_dynasty_frame_cached(
                **keeper_limited_kwargs,
                bench=8,
                minors=12,
                ir=6,
            )

        shallow_values = {str(row["Player"]): float(row["DynastyValue"]) for _, row in shallow.iterrows()}
        deep_values = {str(row["Player"]): float(row["DynastyValue"]) for _, row in deep.iterrows()}
        keeper_limited_values = {
            str(row["Player"]): float(row["DynastyValue"]) for _, row in keeper_limited.iterrows()
        }
        self.assertNotEqual(shallow_values, deep_values)
        self.assertEqual(shallow_values, keeper_limited_values)
        self.assertEqual(deep.attrs["valuation_diagnostics"]["ReplacementRank"], 27)
        self.assertEqual(keeper_limited.attrs["valuation_diagnostics"]["ReplacementRank"], 1)

    def test_points_scoring_uses_explicit_hbp_and_holds_rules(self) -> None:
        bat_rows = [
            {
                "Player": "Hitter HBP",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 27,
                "AB": 10,
                "H": 0,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "HBP": 1,
                "SO": 0,
                "PlayerKey": "hitter-hbp",
                "PlayerEntityKey": "hitter-hbp",
            }
        ]
        pit_rows = [
            {
                "Player": "Reliever HLD",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "RP",
                "Age": 30,
                "IP": 1.0,
                "GS": 0,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 1,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 2,
                "PlayerKey": "reliever-hld",
                "PlayerEntityKey": "reliever-hld",
            }
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ):
            out = app_module._calculate_points_dynasty_frame_cached(
                teams=1,
                horizon=1,
                discount=1.0,
                hit_c=0,
                hit_1b=0,
                hit_2b=0,
                hit_3b=0,
                hit_ss=0,
                hit_ci=0,
                hit_mi=0,
                hit_of=1,
                hit_ut=0,
                pit_p=0,
                pit_sp=0,
                pit_rp=1,
                bench=0,
                minors=0,
                ir=0,
                keeper_limit=None,
                two_way="sum",
                points_valuation_mode="season_total",
                weekly_starts_cap=None,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=None,
                start_year=2026,
                pts_hit_1b=0.0,
                pts_hit_2b=0.0,
                pts_hit_3b=0.0,
                pts_hit_hr=0.0,
                pts_hit_r=0.0,
                pts_hit_rbi=0.0,
                pts_hit_sb=0.0,
                pts_hit_bb=0.0,
                pts_hit_hbp=4.0,
                pts_hit_so=0.0,
                pts_pit_ip=0.0,
                pts_pit_w=0.0,
                pts_pit_l=0.0,
                pts_pit_k=0.0,
                pts_pit_sv=0.0,
                pts_pit_hld=3.0,
                pts_pit_h=0.0,
                pts_pit_er=0.0,
                pts_pit_bb=0.0,
                pts_pit_hbp=-1.0,
            )

        rows_by_player = {str(row["Player"]): row for _, row in out.iterrows()}
        self.assertEqual(float(rows_by_player["Hitter HBP"]["HittingPoints"]), 4.0)
        self.assertEqual(float(rows_by_player["Reliever HLD"]["PitchingPoints"]), 5.0)

    def test_weekly_h2h_points_mode_lowers_fungible_sp_value(self) -> None:
        pit_rows = [
            {
                "Player": "Ace A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "IP": 180.0,
                "GS": 26,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": "ace-a",
                "PlayerEntityKey": "ace-a",
            },
            {
                "Player": "Starter B",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 29,
                "IP": 156.0,
                "GS": 26,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": "starter-b",
                "PlayerEntityKey": "starter-b",
            },
            {
                "Player": "Streamer C",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 30,
                "IP": 78.0,
                "GS": 26,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": "streamer-c",
                "PlayerEntityKey": "streamer-c",
            },
            {
                "Player": "Starter D",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 31,
                "IP": 70.2,
                "GS": 26,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": "starter-d",
                "PlayerEntityKey": "starter-d",
            },
        ]

        base_kwargs = {
            "teams": 1,
            "horizon": 1,
            "discount": 1.0,
            "hit_c": 0,
            "hit_1b": 0,
            "hit_2b": 0,
            "hit_3b": 0,
            "hit_ss": 0,
            "hit_ci": 0,
            "hit_mi": 0,
            "hit_of": 0,
            "hit_ut": 0,
            "pit_p": 0,
            "pit_sp": 2,
            "pit_rp": 0,
            "bench": 0,
            "minors": 0,
            "ir": 0,
            "keeper_limit": None,
            "two_way": "sum",
            "start_year": 2026,
            "pts_hit_1b": 0.0,
            "pts_hit_2b": 0.0,
            "pts_hit_3b": 0.0,
            "pts_hit_hr": 0.0,
            "pts_hit_r": 0.0,
            "pts_hit_rbi": 0.0,
            "pts_hit_sb": 0.0,
            "pts_hit_bb": 0.0,
            "pts_hit_hbp": 0.0,
            "pts_hit_so": 0.0,
            "pts_pit_ip": 3.0,
            "pts_pit_w": 0.0,
            "pts_pit_l": 0.0,
            "pts_pit_k": 0.0,
            "pts_pit_sv": 0.0,
            "pts_pit_hld": 0.0,
            "pts_pit_h": 0.0,
            "pts_pit_er": 0.0,
            "pts_pit_bb": 0.0,
            "pts_pit_hbp": 0.0,
        }

        with patch.object(app_module, "BAT_DATA", []), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ):
            season_total = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                points_valuation_mode="season_total",
                weekly_starts_cap=None,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=None,
            )
            weekly_h2h = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                points_valuation_mode="weekly_h2h",
                weekly_starts_cap=3,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=1,
            )

        season_rows = {str(row["Player"]): row for _, row in season_total.iterrows()}
        weekly_rows = {str(row["Player"]): row for _, row in weekly_h2h.iterrows()}
        self.assertGreater(
            float(season_rows["Starter B"]["RawDynastyValue"]),
            float(weekly_rows["Starter B"]["RawDynastyValue"]),
        )
        self.assertEqual(weekly_h2h.attrs["valuation_diagnostics"]["PointsValuationMode"], "weekly_h2h")
        self.assertEqual(weekly_h2h.attrs["valuation_diagnostics"]["WeeklyStartsCap"], 3)
