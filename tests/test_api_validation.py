import unittest
import types
import sys
import time
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient

import backend.app as app_module


class DynastyYearParsingTests(unittest.TestCase):
    def test_parse_dynasty_years_supports_ranges(self) -> None:
        parsed = app_module._parse_dynasty_years("2028, 2026-2027, bad, 2030-2029")
        self.assertEqual(parsed, [2026, 2027, 2028, 2029, 2030])

    def test_parse_dynasty_years_filters_unknown_years(self) -> None:
        parsed = app_module._parse_dynasty_years("2025-2028,2030", valid_years=[2026, 2028, 2029])
        self.assertEqual(parsed, [2026, 2028])

    def test_resolve_projection_year_filter_accepts_years_only(self) -> None:
        resolved = app_module._resolve_projection_year_filter(
            year=None,
            years="2026,2028-2029",
            valid_years=[2026, 2027, 2028, 2029],
        )
        self.assertSetEqual(resolved or set(), {2026, 2028, 2029})

    def test_resolve_projection_year_filter_intersects_with_single_year(self) -> None:
        resolved = app_module._resolve_projection_year_filter(
            year=2028,
            years="2026-2027,2028",
            valid_years=[2026, 2027, 2028],
        )
        self.assertSetEqual(resolved or set(), {2028})

    def test_resolve_projection_year_filter_returns_empty_set_for_invalid_years_token(self) -> None:
        resolved = app_module._resolve_projection_year_filter(
            year=None,
            years="bad-token",
            valid_years=[2026, 2027, 2028],
        )
        self.assertEqual(resolved, set())


class YearCoercionTests(unittest.TestCase):
    def test_coerce_record_year_handles_numeric_types(self) -> None:
        self.assertEqual(app_module._coerce_record_year(2026), 2026)
        self.assertEqual(app_module._coerce_record_year(2026.0), 2026)
        self.assertEqual(app_module._coerce_record_year("2026"), 2026)
        self.assertEqual(app_module._coerce_record_year("2026.0"), 2026)

    def test_coerce_record_year_rejects_invalid_values(self) -> None:
        self.assertIsNone(app_module._coerce_record_year("2026.5"))
        self.assertIsNone(app_module._coerce_record_year("not-a-year"))
        self.assertIsNone(app_module._coerce_record_year(True))


class ProjectionEndpointValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def setUp(self) -> None:
        app_module._cached_projection_rows.cache_clear()
        app_module._cached_all_projection_rows.cache_clear()
        app_module._projection_sortable_columns_for_dataset.cache_clear()

    def test_bat_limit_must_be_positive(self) -> None:
        response = self.client.get("/api/projections/bat", params={"limit": 0})
        self.assertEqual(response.status_code, 422)

    def test_pitch_offset_cannot_be_negative(self) -> None:
        response = self.client.get("/api/projections/pitch", params={"offset": -1})
        self.assertEqual(response.status_code, 422)

    def test_team_filter_is_case_insensitive(self) -> None:
        sample_rows = [
            {"Player": "Juan Soto", "Team": "NYY", "Year": 2026, "Pos": "OF"},
            {"Player": "Pete Alonso", "Team": "NYM", "Year": 2026, "Pos": "1B"},
        ]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"team": "nyy", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["data"][0]["Player"], "Juan Soto")
        self.assertNotIn("DynastyValue", payload["data"][0])

    def test_team_filter_trims_whitespace(self) -> None:
        sample_rows = [{"Player": "Juan Soto", "Team": "NYY", "Year": 2026, "Pos": "OF"}]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"team": "  nyy  ", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["data"][0]["Player"], "Juan Soto")

    def test_year_filter_handles_float_and_string_year_values(self) -> None:
        sample_rows = [
            {"Player": "Player A", "Team": "NYY", "Year": 2026, "Pos": "OF"},
            {"Player": "Player B", "Team": "NYY", "Year": 2026.0, "Pos": "OF"},
            {"Player": "Player C", "Team": "NYY", "Year": "2026", "Pos": "OF"},
            {"Player": "Player D", "Team": "NYY", "Year": "2026.5", "Pos": "OF"},
        ]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"year": 2026, "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        players = {row["Player"] for row in payload["data"]}
        self.assertSetEqual(players, {"Player A", "Player B", "Player C"})

    def test_years_filter_supports_comma_and_range_syntax(self) -> None:
        sample_rows = [
            {"Player": "Player A", "Team": "NYY", "Year": 2026, "Pos": "OF"},
            {"Player": "Player B", "Team": "NYY", "Year": 2027, "Pos": "OF"},
            {"Player": "Player C", "Team": "NYY", "Year": 2028, "Pos": "OF"},
            {"Player": "Player D", "Team": "NYY", "Year": 2029, "Pos": "OF"},
        ]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "META",
            {"years": [2026, 2027, 2028, 2029]},
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"years": "2026,2028-2029", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        players = {row["Player"] for row in payload["data"]}
        self.assertSetEqual(players, {"Player A", "Player C", "Player D"})

    def test_year_and_years_filters_are_intersected(self) -> None:
        sample_rows = [
            {"Player": "Player A", "Team": "NYY", "Year": 2027, "Pos": "OF"},
            {"Player": "Player B", "Team": "NYY", "Year": 2028, "Pos": "OF"},
        ]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "META",
            {"years": [2027, 2028]},
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"year": 2028, "years": "2027", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["data"], [])

    def test_position_filter_supports_multi_select_tokens(self) -> None:
        sample_rows = [
            {"Player": "Starter", "Team": "SEA", "Year": 2026, "Pos": "SP"},
            {"Player": "Reliever", "Team": "SEA", "Year": 2026, "Pos": "RP"},
            {"Player": "Swingman", "Team": "SEA", "Year": 2026, "Pos": "SP/RP"},
            {"Player": "Catcher", "Team": "SEA", "Year": 2026, "Pos": "C"},
        ]

        with patch.object(app_module, "PIT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/pitch",
                params={"pos": " sp, rp ", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        players = {row["Player"] for row in payload["data"]}
        self.assertSetEqual(players, {"Starter", "Reliever", "Swingman"})

    def test_position_filter_matches_exact_tokens_not_substrings(self) -> None:
        sample_rows = [
            {"Player": "Starter", "Team": "SEA", "Year": 2026, "Pos": "SP"},
            {"Player": "Reliever", "Team": "SEA", "Year": 2026, "Pos": "RP"},
            {"Player": "Catcher", "Team": "SEA", "Year": 2026, "Pos": "C"},
        ]

        with patch.object(app_module, "PIT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/pitch",
                params={"pos": "P", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["data"], [])

    def test_all_endpoint_merges_two_way_rows_with_prefixed_pitching_collisions(self) -> None:
        bat_rows = [
            {
                "Player": "Shohei Ohtani",
                "Team": "LAD",
                "Year": 2026,
                "Pos": "DH",
                "Age": 31,
                "ProjectionsUsed": 3,
                "OldestProjectionDate": "2026-01-05",
                "G": 150,
                "AB": 560,
                "R": 100,
                "H": 162,
                "2B": 28,
                "3B": 2,
                "HR": 45,
                "RBI": 108,
                "SB": 20,
                "BB": 88,
                "SO": 142,
                "AVG": 0.289,
                "OPS": 0.94,
            }
        ]
        pit_rows = [
            {
                "Player": "Shohei Ohtani",
                "Team": "LAD",
                "Year": 2026,
                "Pos": "SP",
                "Age": 31,
                "ProjectionsUsed": 2,
                "OldestProjectionDate": "2025-12-20",
                "GS": 24,
                "IP": 130.0,
                "W": 10,
                "L": 4,
                "K": 160,
                "SV": 0,
                "SVH": 0,
                "ERA": 3.18,
                "WHIP": 1.11,
                "H": 101,
                "HR": 15,
                "BB": 41,
                "ER": 46,
            }
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", pit_rows
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/all",
                params={"include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        row = payload["data"][0]
        self.assertEqual(row["Type"], "H/P")
        self.assertEqual(row["Pos"], "DH/SP")
        self.assertEqual(row["ProjectionsUsed"], 3)
        self.assertEqual(row["OldestProjectionDate"], "2025-12-20")
        self.assertEqual(row["H"], 162)
        self.assertEqual(row["HR"], 45)
        self.assertEqual(row["BB"], 88)
        self.assertEqual(row["PitH"], 101)
        self.assertEqual(row["PitHR"], 15)
        self.assertEqual(row["PitBB"], 41)
        self.assertEqual(row["GS"], 24)
        self.assertEqual(row["IP"], 130.0)

    def test_all_endpoint_keeps_same_name_different_teams_separate(self) -> None:
        bat_rows = [
            {"Player": "John Doe", "Team": "NYY", "Year": 2026, "Pos": "OF", "AB": 500, "H": 140},
            {"Player": "John Doe", "Team": "BOS", "Year": 2026, "Pos": "1B", "AB": 480, "H": 135},
        ]
        pit_rows = [
            {"Player": "John Doe", "Team": "NYY", "Year": 2026, "Pos": "SP", "IP": 120, "H": 100, "HR": 14, "BB": 35}
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", pit_rows
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/all",
                params={"include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        rows_by_team = {row["Team"]: row for row in payload["data"]}
        self.assertEqual(rows_by_team["NYY"]["Type"], "H/P")
        self.assertEqual(rows_by_team["BOS"]["Type"], "H")
        self.assertEqual(rows_by_team["NYY"]["PitH"], 100)
        self.assertIsNone(rows_by_team["BOS"].get("PitH"))

    def test_all_endpoint_supports_combined_team_pos_and_year_filters(self) -> None:
        bat_rows = [
            {"Player": "Dual Threat", "Team": "SEA", "Year": 2026, "Pos": "DH", "AB": 500, "H": 150},
            {"Player": "Dual Threat", "Team": "SEA", "Year": 2027, "Pos": "DH", "AB": 510, "H": 151},
            {"Player": "SEA Bat", "Team": "SEA", "Year": 2026, "Pos": "OF", "AB": 420, "H": 122},
            {"Player": "LAD Bat", "Team": "LAD", "Year": 2026, "Pos": "OF", "AB": 410, "H": 118},
        ]
        pit_rows = [
            {"Player": "Dual Threat", "Team": "SEA", "Year": 2026, "Pos": "SP", "IP": 125, "H": 95, "HR": 11, "BB": 33},
            {"Player": "Dual Threat", "Team": "SEA", "Year": 2027, "Pos": "SP", "IP": 130, "H": 99, "HR": 12, "BB": 35},
            {"Player": "LAD Pitch", "Team": "LAD", "Year": 2026, "Pos": "SP", "IP": 120, "H": 100, "HR": 14, "BB": 31},
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", pit_rows
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/all",
                params={
                    "team": "SEA",
                    "pos": "SP",
                    "year": 2026,
                    "years": "2025-2026",
                    "include_dynasty": "false",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        row = payload["data"][0]
        self.assertEqual(row["Player"], "Dual Threat")
        self.assertEqual(row["Team"], "SEA")
        self.assertEqual(row["Year"], 2026)
        self.assertEqual(row["Type"], "H/P")

    def test_all_endpoint_sorts_and_paginates_server_side(self) -> None:
        bat_rows = [
            {"Player": "Charlie", "Team": "NYM", "Year": 2026, "Pos": "OF", "AB": 400, "H": 110},
            {"Player": "Alpha", "Team": "NYY", "Year": 2026, "Pos": "OF", "AB": 420, "H": 130},
            {"Player": "Bravo", "Team": "BOS", "Year": 2026, "Pos": "OF", "AB": 410, "H": 120},
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", []
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "false",
                    "sort_col": "Player",
                    "sort_dir": "asc",
                    "limit": 1,
                    "offset": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["limit"], 1)
        self.assertEqual(payload["offset"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["Player"], "Bravo")

    def test_invalid_sort_col_returns_422(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "false",
                    "sort_col": "NotARealColumn",
                },
            )

        self.assertEqual(response.status_code, 422)
        detail = response.json().get("detail", "")
        self.assertIn("sort_col", detail)

    def test_paginated_pages_match_full_sorted_order(self) -> None:
        bat_rows = [
            {"Player": "Bravo", "Team": "NYM", "Year": 2026, "Pos": "OF", "AB": 420, "H": 130},
            {"Player": "Echo", "Team": "NYY", "Year": 2026, "Pos": "OF", "AB": 430, "H": 131},
            {"Player": "Alpha", "Team": "BOS", "Year": 2026, "Pos": "OF", "AB": 440, "H": 132},
            {"Player": "Delta", "Team": "LAD", "Year": 2026, "Pos": "OF", "AB": 450, "H": 133},
            {"Player": "Charlie", "Team": "SEA", "Year": 2026, "Pos": "OF", "AB": 460, "H": 134},
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", []
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            full = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "false",
                    "sort_col": "Player",
                    "sort_dir": "asc",
                    "limit": 50,
                    "offset": 0,
                },
            ).json()

            page1 = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "false",
                    "sort_col": "Player",
                    "sort_dir": "asc",
                    "limit": 2,
                    "offset": 0,
                },
            ).json()
            page2 = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "false",
                    "sort_col": "Player",
                    "sort_dir": "asc",
                    "limit": 2,
                    "offset": 2,
                },
            ).json()

        expected = [row["Player"] for row in full["data"][:4]]
        actual = [row["Player"] for row in page1["data"] + page2["data"]]
        self.assertEqual(actual, expected)

    def test_attach_dynasty_values_uses_entity_key_for_ambiguous_name(self) -> None:
        rows = [
            {"Player": "John Doe", "Team": "BOS", "Year": 2026, "PlayerKey": "john-doe", "PlayerEntityKey": "john-doe__bos"},
            {"Player": "John Doe", "Team": "NYY", "Year": 2026, "PlayerKey": "john-doe", "PlayerEntityKey": "john-doe__nyy"},
            {"Player": "Jane Roe", "Team": "SEA", "Year": 2026, "PlayerKey": "jane-roe", "PlayerEntityKey": "jane-roe"},
        ]

        with patch.object(
            app_module,
            "_get_default_dynasty_lookup",
            return_value=(
                {"john-doe__nyy": {"DynastyValue": 11.0}},
                {"jane-roe": {"DynastyValue": 7.5}},
                {"john-doe"},
                [],
            ),
        ):
            enriched = app_module._attach_dynasty_values(rows)

        by_team = {row["Team"]: row for row in enriched}
        self.assertIsNone(by_team["BOS"]["DynastyValue"])
        self.assertEqual(by_team["NYY"]["DynastyValue"], 11.0)
        self.assertEqual(by_team["SEA"]["DynastyValue"], 7.5)
        self.assertEqual(by_team["BOS"]["DynastyMatchStatus"], "no_unique_match")
        self.assertEqual(by_team["NYY"]["DynastyMatchStatus"], "matched")

    def test_large_projection_response_is_gzip_compressed(self) -> None:
        sample_rows = [
            {
                "Player": f"Player {idx}",
                "Team": "NYY",
                "Year": 2026,
                "Pos": "OF",
                "Notes": "x" * 80,
            }
            for idx in range(250)
        ]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"include_dynasty": "false"},
                headers={"Accept-Encoding": "gzip"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-encoding"), "gzip")
        self.assertEqual(response.headers.get("vary"), "Accept-Encoding")

    def test_projection_filters_are_cached_across_paginated_requests(self) -> None:
        sample_rows = [
            {"Player": f"Player {idx}", "Team": "NYY", "Year": 2026, "Pos": "OF"}
            for idx in range(10)
        ]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module,
            "filter_records",
            wraps=app_module.filter_records,
        ) as filter_spy:
            first = self.client.get(
                "/api/projections/bat",
                params={"team": "NYY", "include_dynasty": "false", "limit": 3, "offset": 0},
            )
            second = self.client.get(
                "/api/projections/bat",
                params={"team": "NYY", "include_dynasty": "false", "limit": 3, "offset": 3},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(filter_spy.call_count, 1)


class CalculatorValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def setUp(self) -> None:
        app_module._calculate_common_dynasty_frame_cached.cache_clear()
        app_module._playable_pool_counts_by_year.cache_clear()
        with app_module.CALCULATOR_JOB_LOCK:
            app_module.CALCULATOR_JOBS.clear()

    def test_calculate_request_default_horizon_is_twenty(self) -> None:
        req = app_module.CalculateRequest()
        self.assertEqual(req.horizon, 20)

    def test_mode_must_be_common(self) -> None:
        response = self.client.post("/api/calculate", json={"mode": "league"})
        self.assertEqual(response.status_code, 422)

    def test_rejects_invalid_ip_bounds(self) -> None:
        response = self.client.post("/api/calculate", json={"ip_min": 1200, "ip_max": 1000})
        self.assertEqual(response.status_code, 422)

    def test_rejects_zero_total_hitter_slots(self) -> None:
        response = self.client.post(
            "/api/calculate",
            json={
                "hit_c": 0,
                "hit_1b": 0,
                "hit_2b": 0,
                "hit_3b": 0,
                "hit_ss": 0,
                "hit_ci": 0,
                "hit_mi": 0,
                "hit_of": 0,
                "hit_ut": 0,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_zero_total_pitcher_slots(self) -> None:
        response = self.client.post(
            "/api/calculate",
            json={
                "pit_p": 0,
                "pit_sp": 0,
                "pit_rp": 0,
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_calculate_response_includes_identity_fields(self) -> None:
        fake_out = pd.DataFrame(
            [
                {
                    "Player": "Jane Roe",
                    "Team": "SEA",
                    "Pos": "OF",
                    "Age": 26,
                    "DynastyValue": 5.0,
                    "RawDynastyValue": 6.0,
                    "minor_eligible": False,
                    "Value_2026": 5.0,
                }
            ]
        )

        class FakeSettings:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        def fake_calculate(*args, **kwargs):
            return fake_out

        fake_module = types.SimpleNamespace(
            CommonDynastyRotoSettings=FakeSettings,
            calculate_common_dynasty_values=fake_calculate,
        )

        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ), patch.object(
            app_module,
            "_player_identity_by_name",
            return_value={"Jane Roe": ("jane-roe", "jane-roe")},
        ), patch.dict(
            sys.modules,
            {"dynasty_roto_values": fake_module},
        ):
            response = self.client.post("/api/calculate", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        row = payload["data"][0]
        self.assertEqual(row["PlayerKey"], "jane-roe")
        self.assertEqual(row["PlayerEntityKey"], "jane-roe")
        self.assertEqual(row["DynastyMatchStatus"], "matched")

    def test_rejects_unknown_start_year(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(app_module, "META", {"years": [2026, 2027, 2028]}):
            response = self.client.post("/api/calculate", json={"start_year": 2031})

        self.assertEqual(response.status_code, 422)
        self.assertIn("start_year", response.json()["detail"])

    def test_returns_422_for_unfillable_roster_settings(self) -> None:
        class FakeSettings:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        def fake_calculate(*args, **kwargs):
            raise ValueError("Not enough players (10) to fill required slots (15).")

        fake_module = types.SimpleNamespace(
            CommonDynastyRotoSettings=FakeSettings,
            calculate_common_dynasty_values=fake_calculate,
        )

        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ), patch.dict(
            sys.modules,
            {"dynasty_roto_values": fake_module},
        ):
            response = self.client.post(
                "/api/calculate",
                json={"teams": 20, "bench": 40, "minors": 60, "start_year": 2026},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Not enough players", response.json()["detail"])

    def test_calculate_passes_slot_overrides_and_ir_to_settings(self) -> None:
        fake_out = pd.DataFrame(
            [
                {
                    "Player": "Jane Roe",
                    "Team": "SEA",
                    "Pos": "OF",
                    "Age": 26,
                    "DynastyValue": 5.0,
                    "RawDynastyValue": 6.0,
                    "minor_eligible": False,
                    "Value_2026": 5.0,
                }
            ]
        )
        captured_kwargs: dict = {}

        class FakeSettings:
            def __init__(self, **kwargs) -> None:
                captured_kwargs.update(kwargs)

        def fake_calculate(*args, **kwargs):
            return fake_out

        fake_module = types.SimpleNamespace(
            CommonDynastyRotoSettings=FakeSettings,
            calculate_common_dynasty_values=fake_calculate,
        )

        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ), patch.object(
            app_module,
            "_player_identity_by_name",
            return_value={"Jane Roe": ("jane-roe", "jane-roe")},
        ), patch.dict(
            sys.modules,
            {"dynasty_roto_values": fake_module},
        ):
            response = self.client.post(
                "/api/calculate",
                json={
                    "hit_c": 2,
                    "hit_of": 3,
                    "pit_p": 7,
                    "pit_sp": 1,
                    "pit_rp": 1,
                    "ir": 4,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured_kwargs.get("hitter_slots", {}).get("C"), 2)
        self.assertEqual(captured_kwargs.get("hitter_slots", {}).get("OF"), 3)
        self.assertEqual(captured_kwargs.get("pitcher_slots", {}).get("P"), 7)
        self.assertEqual(captured_kwargs.get("pitcher_slots", {}).get("SP"), 1)
        self.assertEqual(captured_kwargs.get("pitcher_slots", {}).get("RP"), 1)
        self.assertEqual(captured_kwargs.get("ir_slots"), 4)

    def test_meta_includes_calculator_guardrails_payload(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get("/api/meta")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        guardrails = payload.get("calculator_guardrails", {})
        self.assertEqual(guardrails.get("hitters_per_team"), 13)
        self.assertEqual(guardrails.get("pitchers_per_team"), 9)
        self.assertIn("playable_by_year", guardrails)

    def test_calculation_job_lifecycle_success(self) -> None:
        fake_result = {"total": 1, "settings": {}, "data": [{"Player": "Jane Roe"}]}

        with patch.object(
            app_module,
            "_run_calculate_request",
            return_value=fake_result,
        ):
            create = self.client.post("/api/calculate/jobs", json={})
            self.assertEqual(create.status_code, 202)
            job_id = create.json()["job_id"]

            deadline = time.time() + 2.0
            while True:
                status = self.client.get(f"/api/calculate/jobs/{job_id}")
                self.assertEqual(status.status_code, 200)
                payload = status.json()
                if payload["status"] == "completed":
                    break
                if payload["status"] == "failed":
                    self.fail(f"Expected completed job, got failed payload: {payload}")
                if time.time() > deadline:
                    self.fail(f"Timed out waiting for job completion: {payload}")
                time.sleep(0.01)

            self.assertEqual(payload["result"]["total"], 1)

    def test_calculation_job_lifecycle_failure(self) -> None:
        def fake_failure(*args, **kwargs):
            raise HTTPException(status_code=422, detail="Not enough players for selected settings.")

        with patch.object(
            app_module,
            "_run_calculate_request",
            side_effect=fake_failure,
        ):
            create = self.client.post("/api/calculate/jobs", json={})
            self.assertEqual(create.status_code, 202)
            job_id = create.json()["job_id"]

            deadline = time.time() + 2.0
            while True:
                status = self.client.get(f"/api/calculate/jobs/{job_id}")
                self.assertEqual(status.status_code, 200)
                payload = status.json()
                if payload["status"] == "failed":
                    break
                if payload["status"] == "completed":
                    self.fail(f"Expected failed job, got completed payload: {payload}")
                if time.time() > deadline:
                    self.fail(f"Timed out waiting for failed status: {payload}")
                time.sleep(0.01)

            self.assertEqual(payload["error"]["status_code"], 422)
            self.assertIn("Not enough players", payload["error"]["detail"])


if __name__ == "__main__":
    unittest.main()
