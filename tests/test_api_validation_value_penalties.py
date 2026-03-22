import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

import backend.app as app_module
from backend.valuation.active_volume import VolumeEntry, allocate_pitcher_usage_daily


class DynastyValuePenaltyRemovalTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module._calculate_common_dynasty_frame_cached.cache_clear()
        app_module._calculate_points_dynasty_frame_cached.cache_clear()

    def _build_h2h_reserve_model_fixture(self) -> tuple[list[dict], list[dict], dict[str, object]]:
        def hitter_row(
            player: str,
            pos: str,
            games: float,
            hits: float,
            *,
            year: int = 2026,
            age: int = 27,
        ) -> dict:
            key = player.lower().replace(" ", "-")
            return {
                "Player": player,
                "Team": "SEA",
                "Year": year,
                "Pos": pos,
                "Age": age,
                "G": float(games),
                "AB": 300.0 if games > 0 else 0.0,
                "H": float(hits),
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "HBP": 0,
                "SO": 0,
                "PlayerKey": key,
                "PlayerEntityKey": key,
            }

        def pitcher_row(player: str, innings: float, *, year: int = 2026) -> dict:
            key = player.lower().replace(" ", "-")
            return {
                "Player": player,
                "Team": "SEA",
                "Year": year,
                "Pos": "SP",
                "Age": 28,
                "G": 26.0,
                "IP": float(innings),
                "GS": 26.0,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": key,
                "PlayerEntityKey": key,
            }

        bat_rows = [
            hitter_row("Catcher A", "C", 90.0, 120.0),
            hitter_row("OF A", "OF", 90.0, 130.0),
            hitter_row("UT A", "1B", 90.0, 125.0),
            hitter_row("Bench OF", "OF", 90.0, 90.0),
            hitter_row("Bench C", "C", 90.0, 85.0),
            hitter_row("Prospect Catcher", "C", 0.0, 0.0, age=21),
            hitter_row("Prospect Catcher", "C", 100.0, 110.0, year=2027, age=22),
        ]
        pit_rows = [
            pitcher_row("Ace A", 180.0),
            pitcher_row("Starter B", 160.0),
            pitcher_row("Starter C", 140.0),
            pitcher_row("Starter D", 120.0),
            pitcher_row("Starter E", 100.0),
        ]
        kwargs = {
            "teams": 1,
            "horizon": 2,
            "discount": 1.0,
            "hit_c": 1,
            "hit_1b": 0,
            "hit_2b": 0,
            "hit_3b": 0,
            "hit_ss": 0,
            "hit_ci": 0,
            "hit_mi": 0,
            "hit_of": 1,
            "hit_ut": 1,
            "pit_p": 1,
            "pit_sp": 0,
            "pit_rp": 0,
            "bench": 4,
            "minors": 0,
            "ir": 1,
            "keeper_limit": None,
            "two_way": "sum",
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
        return bat_rows, pit_rows, kwargs

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

    def test_points_active_volume_reduces_bench_hitter_under_slot_congestion(self) -> None:
        bat_rows = [
            {
                "Player": "Elite OF",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 27,
                "G": 162.0,
                "AB": 600.0,
                "H": 180.0,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "elite-of",
                "PlayerEntityKey": "elite-of",
            },
            {
                "Player": "Bench OF",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 26,
                "G": 162.0,
                "AB": 540.0,
                "H": 140.0,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "bench-of",
                "PlayerEntityKey": "bench-of",
            },
            {
                "Player": "Replacement OF",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 31,
                "G": 162.0,
                "AB": 500.0,
                "H": 80.0,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "replacement-of",
                "PlayerEntityKey": "replacement-of",
            },
        ]

        kwargs = {
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
            "hit_ut": 0,
            "pit_p": 0,
            "pit_sp": 0,
            "pit_rp": 0,
            "bench": 0,
            "minors": 0,
            "ir": 0,
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
            crowded = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                hit_of=1,
            )
            open_slots = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                hit_of=2,
            )

        crowded_row = crowded[crowded["Player"] == "Bench OF"].iloc[0]
        open_row = open_slots[open_slots["Player"] == "Bench OF"].iloc[0]
        crowded_explain = crowded_row["_ExplainPointsByYear"]["2026"]
        open_explain = open_row["_ExplainPointsByYear"]["2026"]

        self.assertLess(float(crowded_row["RawDynastyValue"]), float(open_row["RawDynastyValue"]))
        self.assertLess(float(crowded_explain["hitting_usage_share"]), 1.0)
        self.assertAlmostEqual(float(open_explain["hitting_usage_share"]), 1.0, places=6)

    def test_points_keeper_limit_preserves_full_in_season_depth_cutoff(self) -> None:
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
        self.assertEqual(deep_values, keeper_limited_values)
        self.assertEqual(deep.attrs["valuation_diagnostics"]["ReplacementRank"], 27)
        self.assertEqual(deep.attrs["valuation_diagnostics"]["InSeasonReplacementRank"], 27)
        self.assertEqual(keeper_limited.attrs["valuation_diagnostics"]["ReplacementRank"], 27)
        self.assertEqual(keeper_limited.attrs["valuation_diagnostics"]["InSeasonReplacementRank"], 27)
        self.assertEqual(keeper_limited.attrs["valuation_diagnostics"]["KeeperContinuationRank"], 1)
        self.assertEqual(keeper_limited.attrs["valuation_diagnostics"]["KeeperContinuationBaselineValue"], 0.0)

    def test_points_keeper_limit_adjusts_future_continuation_without_shrinking_cutoff(self) -> None:
        bat_rows = [
            {
                "Player": "Hitter A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 24,
                "AB": 50,
                "H": 0,
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
                "H": 0,
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
                "H": 0,
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
            {
                "Player": "Hitter D",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 27,
                "AB": 50,
                "H": 0,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "hitter-d",
                "PlayerEntityKey": "hitter-d",
            },
            {
                "Player": "Hitter A",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 25,
                "AB": 50,
                "H": 0,
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
                "Year": 2027,
                "Pos": "OF",
                "Age": 26,
                "AB": 50,
                "H": 0,
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
                "Year": 2027,
                "Pos": "OF",
                "Age": 27,
                "AB": 50,
                "H": 0,
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
            {
                "Player": "Hitter D",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 28,
                "AB": 50,
                "H": 1,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "hitter-d",
                "PlayerEntityKey": "hitter-d",
            },
        ]

        calc_kwargs = {
            "teams": 1,
            "horizon": 2,
            "discount": 0.92,
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
            "bench": 2,
            "minors": 0,
            "ir": 0,
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
            {"years": [2026, 2027]},
        ):
            deep = app_module._calculate_points_dynasty_frame_cached(
                **calc_kwargs,
                keeper_limit=None,
            )
            keeper_limited = app_module._calculate_points_dynasty_frame_cached(
                **calc_kwargs,
                keeper_limit=1,
            )

        deep_diagnostics = deep.attrs["valuation_diagnostics"]
        keeper_diagnostics = keeper_limited.attrs["valuation_diagnostics"]
        deep_values = {str(row["Player"]): float(row["DynastyValue"]) for _, row in deep.iterrows()}
        keeper_values = {str(row["Player"]): float(row["DynastyValue"]) for _, row in keeper_limited.iterrows()}
        deep_raw_values = {str(row["Player"]): float(row["RawDynastyValue"]) for _, row in deep.iterrows()}
        keeper_raw_values = {str(row["Player"]): float(row["RawDynastyValue"]) for _, row in keeper_limited.iterrows()}

        self.assertEqual(deep_diagnostics["ReplacementRank"], 3)
        self.assertEqual(deep_diagnostics["InSeasonReplacementRank"], 3)
        self.assertEqual(keeper_diagnostics["ReplacementRank"], 3)
        self.assertEqual(keeper_diagnostics["InSeasonReplacementRank"], 3)
        self.assertIsNone(deep_diagnostics["KeeperContinuationRank"])
        self.assertEqual(keeper_diagnostics["KeeperContinuationRank"], 1)
        self.assertGreater(float(keeper_diagnostics["KeeperContinuationBaselineValue"]), 0.0)
        self.assertEqual(deep_diagnostics["CenteringMode"], "forced_roster")
        self.assertEqual(keeper_diagnostics["CenteringMode"], "forced_roster")
        self.assertTrue(bool(keeper_diagnostics["ForcedRosterFallbackApplied"]))
        self.assertEqual(deep_raw_values, keeper_raw_values)
        self.assertGreater(keeper_values["Hitter D"], deep_values["Hitter D"])
        hitter_a_keeper = keeper_limited[keeper_limited["Player"] == "Hitter A"].iloc[0]
        self.assertLess(float(hitter_a_keeper["ForcedRosterValue"]), 0.0)

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
                "G": 26.0,
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
                "G": 26.0,
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
                "G": 26.0,
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
                "G": 26.0,
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
                weekly_starts_cap=2,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=1,
            )

        season_rows = {str(row["Player"]): row for _, row in season_total.iterrows()}
        weekly_rows = {str(row["Player"]): row for _, row in weekly_h2h.iterrows()}
        season_explain = season_rows["Streamer C"]["_ExplainPointsByYear"]["2026"]
        weekly_explain = weekly_rows["Streamer C"]["_ExplainPointsByYear"]["2026"]
        self.assertAlmostEqual(float(season_explain["pitching_usage_share"]), 1.0, places=6)
        self.assertLess(float(weekly_explain["pitching_usage_share"]), 1.0)
        self.assertGreater(float(season_explain["pitching_points"]), float(weekly_explain["pitching_points"]))
        self.assertEqual(weekly_h2h.attrs["valuation_diagnostics"]["PointsValuationMode"], "weekly_h2h")
        self.assertEqual(weekly_h2h.attrs["valuation_diagnostics"]["WeeklyStartsCap"], 2)
        diagnostics = weekly_h2h.attrs["valuation_diagnostics"]["WeeklyPitchingByYear"]["2026"]
        self.assertAlmostEqual(float(diagnostics["assigned_starts"]), 52.0, places=4)
        self.assertAlmostEqual(float(diagnostics["capped_start_budget"]), 52.0, places=4)

    def test_weekly_h2h_generic_p_keeps_ace_positive_with_realized_streaming_bonus(self) -> None:
        pit_rows = [
            {
                "Player": "Ace A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "G": 26.0,
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
                "G": 26.0,
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
                "G": 26.0,
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
                "G": 26.0,
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
            "pit_p": 2,
            "pit_sp": 0,
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
        diagnostics = weekly_h2h.attrs["valuation_diagnostics"]["WeeklyPitchingByYear"]["2026"]

        self.assertGreater(float(weekly_rows["Ace A"]["DynastyValue"]), 0.0)
        self.assertGreater(float(weekly_rows["Ace A"]["RawDynastyValue"]), 0.0)
        self.assertAlmostEqual(float(diagnostics["assigned_starts"]), 78.0, places=4)
        self.assertAlmostEqual(float(diagnostics["capped_start_budget"]), 78.0, places=4)
        season_explain = season_rows["Starter D"]["_ExplainPointsByYear"]["2026"]
        starter_d_explain = weekly_rows["Starter D"]["_ExplainPointsByYear"]["2026"]
        self.assertAlmostEqual(float(season_explain["pitching_usage_share"]), 1.0, places=6)
        self.assertLess(float(starter_d_explain["pitching_usage_share"]), 1.0)
        self.assertGreater(float(season_explain["pitching_points"]), float(starter_d_explain["pitching_points"]))
        self.assertAlmostEqual(float(starter_d_explain["pitching_assigned_starts"]), 0.0, places=4)

    def test_weekly_h2h_streaming_ignores_reliever_fractional_starts(self) -> None:
        pit_rows = [
            {
                "Player": "Ace A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "G": 30.0,
                "IP": 180.0,
                "GS": 30.0,
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
                "G": 30.0,
                "IP": 150.0,
                "GS": 30.0,
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
                "Player": "Reliever C",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "RP",
                "Age": 30,
                "G": 60.0,
                "IP": 60.0,
                "GS": 0.1,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": "reliever-c",
                "PlayerEntityKey": "reliever-c",
            },
        ]

        with patch.object(app_module, "BAT_DATA", []), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ):
            weekly_h2h = app_module._calculate_points_dynasty_frame_cached(
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
                hit_of=0,
                hit_ut=0,
                pit_p=1,
                pit_sp=0,
                pit_rp=0,
                bench=0,
                minors=0,
                ir=0,
                keeper_limit=None,
                two_way="sum",
                points_valuation_mode="weekly_h2h",
                weekly_starts_cap=2,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=1,
                start_year=2026,
                pts_hit_1b=0.0,
                pts_hit_2b=0.0,
                pts_hit_3b=0.0,
                pts_hit_hr=0.0,
                pts_hit_r=0.0,
                pts_hit_rbi=0.0,
                pts_hit_sb=0.0,
                pts_hit_bb=0.0,
                pts_hit_hbp=0.0,
                pts_hit_so=0.0,
                pts_pit_ip=3.0,
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

        diagnostics = weekly_h2h.attrs["valuation_diagnostics"]["WeeklyPitchingByYear"]["2026"]
        self.assertAlmostEqual(float(diagnostics["assigned_starts"]), 52.0, places=4)
        self.assertAlmostEqual(float(diagnostics["capped_start_budget"]), 52.0, places=4)
        row = weekly_h2h[weekly_h2h["Player"] == "Reliever C"].iloc[0]
        explain = row["_ExplainPointsByYear"]["2026"]
        self.assertAlmostEqual(float(explain["pitching_assigned_starts"]), 0.0, places=4)

    def test_daily_h2h_points_mode_caps_starts_by_period(self) -> None:
        pit_rows = [
            {
                "Player": "Ace A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "G": 52.0,
                "IP": 156.0,
                "GS": 52.0,
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
                "G": 52.0,
                "IP": 130.0,
                "GS": 52.0,
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
                "G": 52.0,
                "IP": 104.0,
                "GS": 52.0,
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
                "G": 52.0,
                "IP": 78.0,
                "GS": 52.0,
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
            "pit_p": 2,
            "pit_sp": 0,
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
            daily_h2h = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                points_valuation_mode="daily_h2h",
                weekly_starts_cap=2,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=0,
            )

        season_rows = {str(row["Player"]): row for _, row in season_total.iterrows()}
        daily_rows = {str(row["Player"]): row for _, row in daily_h2h.iterrows()}
        diagnostics = daily_h2h.attrs["valuation_diagnostics"]["DailyPitchingByYear"]["2026"]

        self.assertEqual(daily_h2h.attrs["valuation_diagnostics"]["PointsValuationMode"], "daily_h2h")
        self.assertEqual(int(daily_h2h.attrs["valuation_diagnostics"]["SyntheticSeasonDays"]), 182)
        self.assertEqual(int(diagnostics["synthetic_period_days"]), 7)
        self.assertAlmostEqual(float(diagnostics["assigned_starts"]), 52.0, places=4)
        self.assertAlmostEqual(float(diagnostics["selected_held_starts"]), 52.0, places=4)
        self.assertAlmostEqual(float(diagnostics["selected_streamed_starts"]), 0.0, places=4)
        self.assertGreater(float(season_rows["Starter B"]["PitchingPoints"]), float(daily_rows["Starter B"]["PitchingPoints"]))
        self.assertGreater(float(season_rows["Streamer C"]["PitchingPoints"]), float(daily_rows["Streamer C"]["PitchingPoints"]))
        self.assertGreater(float(daily_rows["Ace A"]["DynastyValue"]), 0.0)
        self.assertAlmostEqual(
            float(daily_rows["Streamer C"]["_ExplainPointsByYear"]["2026"]["pitching_assigned_starts"]),
            0.0,
            places=4,
        )

    def test_daily_h2h_models_pitcher_heavy_reserves_from_hitter_off_days(self) -> None:
        bat_rows, pit_rows, base_kwargs = self._build_h2h_reserve_model_fixture()

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
            app_module,
            "META",
            {"years": [2026, 2027]},
        ):
            daily_h2h = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                points_valuation_mode="daily_h2h",
                weekly_starts_cap=3,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=0,
            )

        rows = {str(row["Player"]): row for _, row in daily_h2h.iterrows()}
        diagnostics = daily_h2h.attrs["valuation_diagnostics"]
        pitch_diag = diagnostics["DailyPitchingByYear"]["2026"]

        self.assertEqual(diagnostics["ReplacementRank"], 8)
        self.assertEqual(diagnostics["InSeasonReplacementRank"], 9)
        self.assertEqual(diagnostics["ModeledBenchHittersPerTeam"], 2)
        self.assertEqual(diagnostics["ModeledBenchPitchersPerTeam"], 2)
        self.assertEqual(diagnostics["ModeledHeldPitchersPerTeam"], 3)
        self.assertEqual(diagnostics["ModeledReserveRosterSize"], 8)
        self.assertEqual(diagnostics["ModeledIrRosterSize"], 1)
        self.assertAlmostEqual(float(pitch_diag["selected_held_starts"]), 78.0, places=4)
        self.assertAlmostEqual(float(pitch_diag["selected_streamed_starts"]), 0.0, places=4)
        self.assertGreater(float(rows["Ace A"]["DynastyValue"]), float(rows["Catcher A"]["DynastyValue"]))
        self.assertEqual(float(rows["Prospect Catcher"]["SelectedPoints"]), 0.0)

    def test_daily_h2h_generic_p_uses_lower_starter_replacement_when_starters_are_scarcer(self) -> None:
        def pitcher_row(player: str, pos: str, games: float, innings: float, starts: float) -> dict:
            key = player.lower().replace(" ", "-")
            return {
                "Player": player,
                "Team": "SEA",
                "Year": 2026,
                "Pos": pos,
                "Age": 28,
                "G": float(games),
                "IP": float(innings),
                "GS": float(starts),
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": key,
                "PlayerEntityKey": key,
            }

        pit_rows = [
            pitcher_row("Starter A", "SP", 30.0, 150.0, 30.0),
            pitcher_row("Starter B", "SP", 30.0, 140.0, 30.0),
            pitcher_row("Starter C", "SP", 30.0, 130.0, 30.0),
            pitcher_row("Starter D", "SP", 30.0, 107.0, 30.0),
            pitcher_row("Starter E", "SP", 30.0, 60.0, 30.0),
            pitcher_row("Reliever A", "RP", 70.0, 100.0, 0.0),
            pitcher_row("Reliever B", "RP", 70.0, 97.0, 0.0),
            pitcher_row("Reliever C", "RP", 70.0, 93.0, 0.0),
        ]

        with patch.object(app_module, "BAT_DATA", []), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ):
            daily_h2h = app_module._calculate_points_dynasty_frame_cached(
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
                hit_of=0,
                hit_ut=0,
                pit_p=1,
                pit_sp=0,
                pit_rp=0,
                bench=3,
                minors=0,
                ir=0,
                keeper_limit=None,
                two_way="sum",
                points_valuation_mode="daily_h2h",
                weekly_starts_cap=10,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=0,
                start_year=2026,
                pts_hit_1b=0.0,
                pts_hit_2b=0.0,
                pts_hit_3b=0.0,
                pts_hit_hr=0.0,
                pts_hit_r=0.0,
                pts_hit_rbi=0.0,
                pts_hit_sb=0.0,
                pts_hit_bb=0.0,
                pts_hit_hbp=0.0,
                pts_hit_so=0.0,
                pts_pit_ip=1.0,
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

        diagnostics = daily_h2h.attrs["valuation_diagnostics"]
        starter_replacement = float(diagnostics["ModeledStarterPitcherReplacement"])
        starter_a = daily_h2h[daily_h2h["Player"] == "Starter A"].iloc[0]["_ExplainPointsByYear"]["2026"]
        unassigned_pitcher_points = max(
            float(row["_ExplainPointsByYear"]["2026"]["pitching_points"])
            for _, row in daily_h2h.iterrows()
            if row["_ExplainPointsByYear"]["2026"]["pitching_assignment_slot"] is None
        )

        self.assertGreaterEqual(starter_replacement, 0.0)
        self.assertLessEqual(starter_replacement, unassigned_pitcher_points)
        if starter_replacement > 0.0:
            self.assertAlmostEqual(
                float(starter_a["pitching_assignment_replacement"]),
                starter_replacement,
                places=4,
            )
        else:
            self.assertGreater(float(starter_a["pitching_assignment_replacement"]), starter_replacement)

    def test_daily_pitcher_allocator_prefers_best_held_start_over_earlier_worse_start(self) -> None:
        entries = [
            VolumeEntry(player_id="ace-a", projected_volume=1.0, quality=10.0, slots={"P"}, year=2026),
            VolumeEntry(player_id="worse-b", projected_volume=1.0, quality=5.0, slots={"P"}, year=2026),
        ]
        start_volume_by_player = {"ace-a": 1.0, "worse-b": 1.0}

        def fake_generate_days(*, player_id: str, tag: str, **_kwargs) -> list[int]:
            if tag == "pit-start":
                return [1] if player_id == "ace-a" else [0]
            return []

        with patch("backend.valuation.active_volume._generate_synthetic_days", side_effect=fake_generate_days):
            allocation = allocate_pitcher_usage_daily(
                entries,
                start_volume_by_player=start_volume_by_player,
                slot_capacity={"P": 7.0},
                capped_start_budget=1.0,
                held_player_ids={"ace-a", "worse-b"},
                streaming_adds_per_period=0,
                allow_same_day_starts_overflow=False,
                total_days=7,
                period_days=7,
            )

        self.assertAlmostEqual(float(allocation.assigned_starts_by_player["ace-a"]), 1.0, places=4)
        self.assertAlmostEqual(float(allocation.assigned_starts_by_player["worse-b"]), 0.0, places=4)

    def test_daily_pitcher_allocator_overflow_only_adds_same_day_extra_starts(self) -> None:
        entries = [
            VolumeEntry(player_id="starter-a", projected_volume=1.0, quality=10.0, slots={"P"}, year=2026),
            VolumeEntry(player_id="starter-b", projected_volume=1.0, quality=9.0, slots={"P"}, year=2026),
            VolumeEntry(player_id="starter-c", projected_volume=1.0, quality=8.0, slots={"P"}, year=2026),
        ]
        start_volume_by_player = {
            "starter-a": 1.0,
            "starter-b": 1.0,
            "starter-c": 1.0,
        }

        def fake_generate_days(*, player_id: str, tag: str, **_kwargs) -> list[int]:
            if tag != "pit-start":
                return []
            if player_id in {"starter-a", "starter-b"}:
                return [0]
            return [1]

        with patch("backend.valuation.active_volume._generate_synthetic_days", side_effect=fake_generate_days):
            no_overflow = allocate_pitcher_usage_daily(
                entries,
                start_volume_by_player=start_volume_by_player,
                slot_capacity={"P": 14.0},
                capped_start_budget=1.0,
                held_player_ids={"starter-a", "starter-b", "starter-c"},
                streaming_adds_per_period=0,
                allow_same_day_starts_overflow=False,
                total_days=7,
                period_days=7,
            )
            with_overflow = allocate_pitcher_usage_daily(
                entries,
                start_volume_by_player=start_volume_by_player,
                slot_capacity={"P": 14.0},
                capped_start_budget=1.0,
                held_player_ids={"starter-a", "starter-b", "starter-c"},
                streaming_adds_per_period=0,
                allow_same_day_starts_overflow=True,
                total_days=7,
                period_days=7,
            )

        self.assertAlmostEqual(float(no_overflow.total_assigned_starts), 1.0, places=4)
        self.assertAlmostEqual(float(no_overflow.selected_overflow_starts or 0.0), 0.0, places=4)
        self.assertAlmostEqual(float(with_overflow.total_assigned_starts), 2.0, places=4)
        self.assertAlmostEqual(float(with_overflow.selected_overflow_starts or 0.0), 1.0, places=4)

    def test_weekly_h2h_uses_modeled_reserve_depth_without_daily_hold_allocator(self) -> None:
        bat_rows, pit_rows, base_kwargs = self._build_h2h_reserve_model_fixture()

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
            app_module,
            "META",
            {"years": [2026, 2027]},
        ):
            weekly_h2h = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                points_valuation_mode="weekly_h2h",
                weekly_starts_cap=3,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=0,
            )

        diagnostics = weekly_h2h.attrs["valuation_diagnostics"]
        pitch_diag = diagnostics["WeeklyPitchingByYear"]["2026"]

        self.assertEqual(diagnostics["ReplacementRank"], 8)
        self.assertEqual(diagnostics["InSeasonReplacementRank"], 9)
        self.assertEqual(diagnostics["ModeledBenchHittersPerTeam"], 2)
        self.assertEqual(diagnostics["ModeledBenchPitchersPerTeam"], 2)
        self.assertEqual(diagnostics["ModeledHeldPitchersPerTeam"], 3)
        self.assertEqual(diagnostics["ModeledReserveRosterSize"], 8)
        self.assertIsNone(pitch_diag["selected_held_starts"])
        self.assertIsNone(pitch_diag["selected_streamed_starts"])
        self.assertIsNone(pitch_diag["streaming_adds_per_period"])

    def test_season_total_points_keeps_full_depth_cutoff_instead_of_h2h_reserve_model(self) -> None:
        bat_rows, pit_rows, base_kwargs = self._build_h2h_reserve_model_fixture()

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
            app_module,
            "META",
            {"years": [2026, 2027]},
        ):
            season_total = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                points_valuation_mode="season_total",
                weekly_starts_cap=None,
                allow_same_day_starts_overflow=False,
                weekly_acquisition_cap=None,
            )

        diagnostics = season_total.attrs["valuation_diagnostics"]
        pitch_diag = diagnostics["PitcherUsageByYear"]["2026"]

        self.assertEqual(diagnostics["ReplacementRank"], 9)
        self.assertEqual(diagnostics["InSeasonReplacementRank"], 9)
        self.assertIsNone(diagnostics.get("ModeledBenchHittersPerTeam"))
        self.assertIsNone(diagnostics.get("ModeledBenchPitchersPerTeam"))
        self.assertIsNone(pitch_diag["modeled_bench_hitters_per_team"])
        self.assertIsNone(pitch_diag["modeled_bench_pitchers_per_team"])
        self.assertIsNone(pitch_diag["modeled_held_pitchers_per_team"])

    def test_points_ip_max_hard_cap_trims_excess_pitcher_value(self) -> None:
        pit_rows = [
            {
                "Player": "Ace A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "G": 30.0,
                "IP": 180.0,
                "GS": 30.0,
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
                "G": 30.0,
                "IP": 160.0,
                "GS": 30.0,
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
                "Player": "Starter C",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 30,
                "G": 30.0,
                "IP": 120.0,
                "GS": 30.0,
                "H": 0,
                "ER": 0,
                "BB": 0,
                "HBP": 0,
                "K": 0,
                "W": 0,
                "L": 0,
                "SV": 0,
                "HLD": 0,
                "PlayerKey": "starter-c",
                "PlayerEntityKey": "starter-c",
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
            "pit_p": 2,
            "pit_sp": 0,
            "pit_rp": 0,
            "bench": 0,
            "minors": 0,
            "ir": 0,
            "keeper_limit": None,
            "two_way": "sum",
            "start_year": 2026,
            "points_valuation_mode": "season_total",
            "weekly_starts_cap": None,
            "allow_same_day_starts_overflow": False,
            "weekly_acquisition_cap": None,
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
            no_cap = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                ip_max=None,
            )
            hard_cap = app_module._calculate_points_dynasty_frame_cached(
                **base_kwargs,
                ip_max=240.0,
            )

        no_cap_rows = {str(row["Player"]): row for _, row in no_cap.iterrows()}
        hard_cap_rows = {str(row["Player"]): row for _, row in hard_cap.iterrows()}
        diagnostics = hard_cap.attrs["valuation_diagnostics"]["PitcherUsageByYear"]["2026"]
        ace_explain = hard_cap_rows["Ace A"]["_ExplainPointsByYear"]["2026"]
        starter_c_explain = hard_cap_rows["Starter C"]["_ExplainPointsByYear"]["2026"]

        self.assertTrue(bool(diagnostics["ip_cap_binding"]))
        self.assertAlmostEqual(float(diagnostics["ip_cap_budget"]), 240.0, places=4)
        self.assertAlmostEqual(float(diagnostics["assigned_pitcher_ip"]), 240.0, places=4)
        self.assertAlmostEqual(float(diagnostics["requested_pitcher_ip_pre_cap"]), 460.0, places=4)
        self.assertGreater(float(no_cap_rows["Starter C"]["PitchingPoints"]), float(hard_cap_rows["Starter C"]["PitchingPoints"]))
        self.assertGreater(float(no_cap_rows["Starter B"]["PitchingPoints"]), float(hard_cap_rows["Starter B"]["PitchingPoints"]))
        self.assertAlmostEqual(float(ace_explain["pitching_ip_usage_share"]), 1.0, places=6)
        self.assertLess(float(starter_c_explain["pitching_ip_usage_share"]), 1.0)
        self.assertAlmostEqual(float(ace_explain["pitching_assigned_ip"]), 180.0, places=4)
        self.assertAlmostEqual(float(starter_c_explain["pitching_assigned_ip"]), 0.0, places=4)

    def test_points_mode_bench_stash_relief_reduces_negative_hold_cost(self) -> None:
        bat_rows = [
            {
                "Player": "Starter A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 28,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "starter-a",
                "PlayerEntityKey": "starter-a",
            },
            {
                "Player": "Starter A",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 29,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "starter-a",
                "PlayerEntityKey": "starter-a",
            },
            {
                "Player": "Bench Prospect",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 22,
                "AB": 50,
                "H": 5,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "bench-prospect",
                "PlayerEntityKey": "bench-prospect",
            },
            {
                "Player": "Bench Prospect",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 23,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "bench-prospect",
                "PlayerEntityKey": "bench-prospect",
            },
            {
                "Player": "Replacement C",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 30,
                "AB": 100,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "replacement-c",
                "PlayerEntityKey": "replacement-c",
            },
            {
                "Player": "Replacement C",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 31,
                "AB": 100,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "replacement-c",
                "PlayerEntityKey": "replacement-c",
            },
        ]

        kwargs = {
            "teams": 1,
            "horizon": 2,
            "discount": 0.94,
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
            "minors": 0,
            "ir": 0,
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
            {"years": [2026, 2027]},
        ):
            without_relief = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                bench=1,
                enable_bench_stash_relief=False,
                bench_negative_penalty=0.5,
            )
            with_relief = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                bench=1,
                enable_bench_stash_relief=True,
                bench_negative_penalty=0.5,
            )

        without_row = without_relief[without_relief["Player"] == "Bench Prospect"].iloc[0]
        with_row = with_relief[with_relief["Player"] == "Bench Prospect"].iloc[0]
        self.assertAlmostEqual(float(without_row["Value_2026"]), -5.0, places=4)
        self.assertAlmostEqual(float(with_row["Value_2026"]), -2.5, places=4)
        self.assertGreater(float(with_row["RawDynastyValue"]), float(without_row["RawDynastyValue"]))

    def test_points_mode_ir_stash_relief_reduces_negative_hold_cost(self) -> None:
        bat_rows = [
            {
                "Player": "Starter A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 28,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "starter-a",
                "PlayerEntityKey": "starter-a",
            },
            {
                "Player": "Starter A",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 29,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "starter-a",
                "PlayerEntityKey": "starter-a",
            },
            {
                "Player": "Injured Prospect",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 23,
                "AB": 10,
                "H": 5,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "injured-prospect",
                "PlayerEntityKey": "injured-prospect",
            },
            {
                "Player": "Injured Prospect",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 24,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "injured-prospect",
                "PlayerEntityKey": "injured-prospect",
            },
            {
                "Player": "Replacement C",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 30,
                "AB": 100,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "replacement-c",
                "PlayerEntityKey": "replacement-c",
            },
            {
                "Player": "Replacement C",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 31,
                "AB": 100,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "replacement-c",
                "PlayerEntityKey": "replacement-c",
            },
        ]

        kwargs = {
            "teams": 1,
            "horizon": 2,
            "discount": 0.94,
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
            "bench": 0,
            "minors": 0,
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
            {"years": [2026, 2027]},
        ):
            without_relief = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                ir=1,
                enable_ir_stash_relief=False,
                ir_negative_penalty=0.2,
            )
            with_relief = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                ir=1,
                enable_ir_stash_relief=True,
                ir_negative_penalty=0.2,
            )

        without_row = without_relief[without_relief["Player"] == "Injured Prospect"].iloc[0]
        with_row = with_relief[with_relief["Player"] == "Injured Prospect"].iloc[0]
        self.assertAlmostEqual(float(without_row["Value_2026"]), -5.0, places=4)
        self.assertAlmostEqual(float(with_row["Value_2026"]), -1.0, places=4)
        self.assertGreater(float(with_row["RawDynastyValue"]), float(without_row["RawDynastyValue"]))

    def test_points_mode_prospect_risk_adjustment_discounts_minor_eligible_future_value(self) -> None:
        bat_rows = [
            {
                "Player": "Starter A",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 28,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "starter-a",
                "PlayerEntityKey": "starter-a",
            },
            {
                "Player": "Starter A",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 29,
                "AB": 100,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "starter-a",
                "PlayerEntityKey": "starter-a",
            },
            {
                "Player": "Minor Prospect",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 22,
                "AB": 20,
                "H": 8,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "minor-prospect",
                "PlayerEntityKey": "minor-prospect",
            },
            {
                "Player": "Minor Prospect",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 23,
                "AB": 40,
                "H": 20,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "minor-prospect",
                "PlayerEntityKey": "minor-prospect",
            },
            {
                "Player": "Replacement C",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 30,
                "AB": 100,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "replacement-c",
                "PlayerEntityKey": "replacement-c",
            },
            {
                "Player": "Replacement C",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 31,
                "AB": 100,
                "H": 10,
                "2B": 0,
                "3B": 0,
                "HR": 0,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "replacement-c",
                "PlayerEntityKey": "replacement-c",
            },
        ]

        kwargs = {
            "teams": 1,
            "horizon": 2,
            "discount": 0.94,
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
            "bench": 0,
            "minors": 0,
            "ir": 0,
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
            {"years": [2026, 2027]},
        ):
            without_risk = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                enable_prospect_risk_adjustment=False,
            )
            with_risk = app_module._calculate_points_dynasty_frame_cached(
                **kwargs,
                enable_prospect_risk_adjustment=True,
            )

        without_row = without_risk[without_risk["Player"] == "Minor Prospect"].iloc[0]
        with_row = with_risk[with_risk["Player"] == "Minor Prospect"].iloc[0]
        self.assertTrue(bool(with_row["minor_eligible"]))
        self.assertGreater(float(without_row["RawDynastyValue"]), float(with_row["RawDynastyValue"]))
