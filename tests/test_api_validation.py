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


class ProjectionConfidenceAdjustmentTests(unittest.TestCase):
    def test_multiplier_downweights_uncertain_positive_upside(self) -> None:
        row = {
            "DynastyValue": 12.5,
            "ProjectionsUsed": 1,
            "Age": 22,
            "minor_eligible": True,
            "Pos": "1B",
            "Value_2026": -1.0,
        }
        context_entry = {"projections_used": 1, "ab": 0.0, "ip": 0.0, "pos": "1B"}

        multiplier = app_module._projection_confidence_multiplier(
            row,
            context_entry=context_entry,
            start_year=2026,
        )

        self.assertLess(multiplier, 1.0)
        self.assertGreaterEqual(multiplier, 0.55)

    def test_multiplier_keeps_negative_non_pitcher_values_intact(self) -> None:
        row = {
            "DynastyValue": -1.3,
            "ProjectionsUsed": 1,
            "Age": 27,
            "minor_eligible": False,
            "Pos": "OF",
            "Value_2026": -0.8,
        }
        context_entry = {"projections_used": 1, "ab": 140.0, "ip": 0.0, "pos": "OF"}

        multiplier = app_module._projection_confidence_multiplier(
            row,
            context_entry=context_entry,
            start_year=2026,
        )

        self.assertEqual(multiplier, 1.0)

    def test_multiplier_applies_mild_uplift_to_durable_negative_sp(self) -> None:
        row = {
            "DynastyValue": -2.1,
            "ProjectionsUsed": 1,
            "Age": 30,
            "minor_eligible": False,
            "Pos": "SP",
            "Value_2026": -0.9,
        }
        context_entry = {"projections_used": 1, "ab": 0.0, "ip": 158.0, "pos": "SP"}

        multiplier = app_module._projection_confidence_multiplier(
            row,
            context_entry=context_entry,
            start_year=2026,
        )

        self.assertEqual(multiplier, 0.92)


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

    def test_attach_dynasty_values_disambiguates_same_name_by_team(self) -> None:
        rows = [
            {
                "Player": "Max Muncy",
                "Team": "Athletics",
                "Age": 23,
                "Year": 2026,
                "PlayerKey": "max-muncy",
                "PlayerEntityKey": "max-muncy__athletics",
            },
            {
                "Player": "Max Muncy",
                "Team": "Dodgers",
                "Age": 35,
                "Year": 2026,
                "PlayerKey": "max-muncy",
                "PlayerEntityKey": "max-muncy__dodgers",
            },
        ]
        dynasty_frame = pd.DataFrame(
            [
                {
                    "Player": "Max Muncy",
                    "Team": "Athletics",
                    "Age": 23,
                    "DynastyValue": -4.42,
                    "Value_2026": -1.23,
                }
            ]
        )

        app_module._get_default_dynasty_lookup.cache_clear()
        try:
            with patch.object(
                app_module,
                "_calculate_common_dynasty_frame_cached",
                return_value=dynasty_frame,
            ), patch.object(app_module, "BAT_DATA", rows), patch.object(app_module, "PIT_DATA", []):
                enriched = app_module._attach_dynasty_values(rows)
        finally:
            app_module._get_default_dynasty_lookup.cache_clear()

        by_team = {row["Team"]: row for row in enriched}
        self.assertEqual(by_team["Athletics"]["DynastyMatchStatus"], "matched")
        self.assertEqual(by_team["Athletics"]["DynastyValue"], -4.42)
        self.assertEqual(by_team["Dodgers"]["DynastyMatchStatus"], "no_unique_match")
        self.assertIsNone(by_team["Dodgers"]["DynastyValue"])

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

    def test_projection_filters_are_cached_across_sort_variants(self) -> None:
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
            asc = self.client.get(
                "/api/projections/bat",
                params={
                    "team": "NYY",
                    "include_dynasty": "false",
                    "sort_col": "Player",
                    "sort_dir": "asc",
                    "limit": 3,
                    "offset": 0,
                },
            )
            desc = self.client.get(
                "/api/projections/bat",
                params={
                    "team": "NYY",
                    "include_dynasty": "false",
                    "sort_col": "Player",
                    "sort_dir": "desc",
                    "limit": 3,
                    "offset": 0,
                },
            )

        self.assertEqual(asc.status_code, 200)
        self.assertEqual(desc.status_code, 200)
        asc_players = [row["Player"] for row in asc.json()["data"]]
        desc_players = [row["Player"] for row in desc.json()["data"]]
        self.assertNotEqual(asc_players, desc_players)
        self.assertEqual(filter_spy.call_count, 1)

    def test_bat_endpoint_career_totals_aggregates_stats_across_years(self) -> None:
        bat_rows = [
            {
                "Player": "Career Bat",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 24,
                "ProjectionsUsed": 3,
                "OldestProjectionDate": "2026-01-10",
                "AB": 500.0,
                "H": 150.0,
                "2B": 30.0,
                "3B": 2.0,
                "HR": 25.0,
                "BB": 60.0,
                "HBP": 5.0,
                "SF": 4.0,
                "R": 85.0,
                "RBI": 92.0,
                "SB": 14.0,
                "SO": 120.0,
            },
            {
                "Player": "Career Bat",
                "Team": "SEA",
                "Year": 2027,
                "Pos": "OF",
                "Age": 25,
                "ProjectionsUsed": 2,
                "OldestProjectionDate": "2025-12-20",
                "AB": 550.0,
                "H": 160.0,
                "2B": 32.0,
                "3B": 1.0,
                "HR": 27.0,
                "BB": 65.0,
                "HBP": 6.0,
                "SF": 5.0,
                "R": 90.0,
                "RBI": 98.0,
                "SB": 16.0,
                "SO": 130.0,
            },
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"career_totals": "true", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        row = payload["data"][0]
        self.assertEqual(row["Player"], "Career Bat")
        self.assertEqual(row["Years"], "2026-2027")
        self.assertEqual(row["YearStart"], 2026)
        self.assertEqual(row["YearEnd"], 2027)
        self.assertIsNone(row["Year"])
        self.assertEqual(row["AB"], 1050.0)
        self.assertEqual(row["H"], 310.0)
        self.assertEqual(row["HR"], 52.0)
        self.assertEqual(row["ProjectionsUsed"], 5)
        self.assertEqual(row["OldestProjectionDate"], "2025-12-20")
        self.assertAlmostEqual(row["AVG"], 310.0 / 1050.0, places=6)

        total_tb = 310.0 + 62.0 + (2.0 * 3.0) + (3.0 * 52.0)
        total_obp = (310.0 + 125.0 + 11.0) / (1050.0 + 125.0 + 11.0 + 9.0)
        total_ops = total_obp + (total_tb / 1050.0)
        self.assertAlmostEqual(row["OPS"], total_ops, places=6)

    def test_all_endpoint_career_totals_merges_two_way_player(self) -> None:
        bat_rows = [
            {
                "Player": "Dual Star",
                "Team": "LAD",
                "Year": 2026,
                "Pos": "DH",
                "Age": 28,
                "ProjectionsUsed": 2,
                "OldestProjectionDate": "2026-01-05",
                "AB": 520.0,
                "H": 150.0,
                "2B": 28.0,
                "3B": 2.0,
                "HR": 34.0,
                "BB": 70.0,
                "HBP": 4.0,
                "SF": 4.0,
                "R": 92.0,
                "RBI": 101.0,
                "SB": 15.0,
                "SO": 130.0,
            },
            {
                "Player": "Dual Star",
                "Team": "LAD",
                "Year": 2027,
                "Pos": "DH",
                "Age": 29,
                "ProjectionsUsed": 2,
                "OldestProjectionDate": "2025-12-30",
                "AB": 510.0,
                "H": 148.0,
                "2B": 27.0,
                "3B": 1.0,
                "HR": 32.0,
                "BB": 68.0,
                "HBP": 3.0,
                "SF": 3.0,
                "R": 90.0,
                "RBI": 98.0,
                "SB": 14.0,
                "SO": 128.0,
            },
        ]
        pit_rows = [
            {
                "Player": "Dual Star",
                "Team": "LAD",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "ProjectionsUsed": 1,
                "OldestProjectionDate": "2026-01-20",
                "GS": 24.0,
                "IP": 140.0,
                "W": 11.0,
                "L": 5.0,
                "K": 170.0,
                "SV": 0.0,
                "SVH": 0.0,
                "ER": 50.0,
                "H": 120.0,
                "HR": 16.0,
                "BB": 42.0,
            },
            {
                "Player": "Dual Star",
                "Team": "LAD",
                "Year": 2027,
                "Pos": "SP",
                "Age": 29,
                "ProjectionsUsed": 2,
                "OldestProjectionDate": "2026-02-01",
                "GS": 26.0,
                "IP": 150.0,
                "W": 12.0,
                "L": 6.0,
                "K": 180.0,
                "SV": 0.0,
                "SVH": 0.0,
                "ER": 54.0,
                "H": 126.0,
                "HR": 18.0,
                "BB": 45.0,
            },
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
                params={"career_totals": "true", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        row = payload["data"][0]
        self.assertEqual(row["Player"], "Dual Star")
        self.assertEqual(row["Type"], "H/P")
        self.assertEqual(row["Pos"], "DH/SP")
        self.assertEqual(row["Years"], "2026-2027")
        self.assertEqual(row["YearStart"], 2026)
        self.assertEqual(row["YearEnd"], 2027)
        self.assertIsNone(row["Year"])
        self.assertEqual(row["H"], 298.0)
        self.assertEqual(row["HR"], 66.0)
        self.assertEqual(row["PitH"], 246.0)
        self.assertEqual(row["PitHR"], 34.0)
        self.assertEqual(row["PitBB"], 87.0)
        self.assertEqual(row["K"], 350.0)
        self.assertEqual(row["ProjectionsUsed"], 7)
        self.assertEqual(row["OldestProjectionDate"], "2025-12-30")


class CalculatorValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def setUp(self) -> None:
        app_module._calculate_common_dynasty_frame_cached.cache_clear()
        app_module._calculate_points_dynasty_frame_cached.cache_clear()
        app_module._playable_pool_counts_by_year.cache_clear()
        with app_module.CALCULATOR_JOB_LOCK:
            app_module.CALCULATOR_JOBS.clear()
        with app_module.CALC_RESULT_CACHE_LOCK:
            app_module.CALC_RESULT_CACHE.clear()
            app_module.CALC_RESULT_CACHE_ORDER.clear()
        with app_module.REQUEST_RATE_LIMIT_LOCK:
            app_module.REQUEST_RATE_LIMIT_BUCKETS.clear()

    def test_local_result_cache_reorders_on_get_for_lru_eviction(self) -> None:
        with patch.object(app_module, "_redis_client", return_value=None), patch.object(
            app_module,
            "CALC_RESULT_CACHE_MAX_ENTRIES",
            2,
        ):
            app_module._result_cache_set("a", {"value": "A"})
            app_module._result_cache_set("b", {"value": "B"})
            cached = app_module._result_cache_get("a")
            app_module._result_cache_set("c", {"value": "C"})

        self.assertEqual(cached, {"value": "A"})
        self.assertIn("a", app_module.CALC_RESULT_CACHE)
        self.assertIn("c", app_module.CALC_RESULT_CACHE)
        self.assertNotIn("b", app_module.CALC_RESULT_CACHE)

    def test_local_result_cache_upsert_deduplicates_order_queue(self) -> None:
        with patch.object(app_module, "_redis_client", return_value=None):
            app_module._result_cache_set("same-key", {"value": 1})
            app_module._result_cache_set("same-key", {"value": 2})

        self.assertEqual(list(app_module.CALC_RESULT_CACHE_ORDER), ["same-key"])
        self.assertEqual(app_module._result_cache_get("same-key"), {"value": 2})

    def test_health_endpoint_reports_runtime_summary(self) -> None:
        with app_module.CALCULATOR_JOB_LOCK:
            app_module.CALCULATOR_JOBS.clear()
            app_module.CALCULATOR_JOBS["job-queued"] = {"status": "queued", "job_id": "job-queued"}
            app_module.CALCULATOR_JOBS["job-failed"] = {"status": "failed", "job_id": "job-failed"}
        with app_module.CALC_RESULT_CACHE_LOCK:
            app_module.CALC_RESULT_CACHE.clear()
            app_module.CALC_RESULT_CACHE_ORDER.clear()
            app_module.CALC_RESULT_CACHE["cache-key"] = (time.time() + 60.0, {"value": 1})
            app_module.CALC_RESULT_CACHE_ORDER.append("cache-key")

        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module,
            "BAT_DATA",
            [{"Player": "Hitter"}],
        ), patch.object(
            app_module,
            "PIT_DATA",
            [{"Player": "Pitcher 1"}, {"Player": "Pitcher 2"}],
        ):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(payload.get("projection_rows", {}).get("bat"), 1)
        self.assertEqual(payload.get("projection_rows", {}).get("pitch"), 2)
        self.assertEqual(payload.get("jobs", {}).get("total"), 2)
        self.assertEqual(payload.get("jobs", {}).get("queued"), 1)
        self.assertEqual(payload.get("jobs", {}).get("failed"), 1)
        self.assertEqual(payload.get("result_cache", {}).get("local_entries"), 1)
        self.assertIn("timestamp", payload)

    def test_calculate_request_default_horizon_is_twenty(self) -> None:
        req = app_module.CalculateRequest()
        self.assertEqual(req.horizon, 20)
        self.assertEqual(req.minors, app_module.COMMON_DEFAULT_MINOR_SLOTS)

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

    def test_points_mode_requires_non_zero_scoring_rule(self) -> None:
        response = self.client.post(
            "/api/calculate",
            json={
                "scoring_mode": "points",
                "pts_hit_1b": 0,
                "pts_hit_2b": 0,
                "pts_hit_3b": 0,
                "pts_hit_hr": 0,
                "pts_hit_r": 0,
                "pts_hit_rbi": 0,
                "pts_hit_sb": 0,
                "pts_hit_bb": 0,
                "pts_hit_so": 0,
                "pts_pit_ip": 0,
                "pts_pit_w": 0,
                "pts_pit_l": 0,
                "pts_pit_k": 0,
                "pts_pit_sv": 0,
                "pts_pit_svh": 0,
                "pts_pit_h": 0,
                "pts_pit_er": 0,
                "pts_pit_bb": 0,
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

    def test_returns_422_for_slot_eligibility_shortage(self) -> None:
        class FakeSettings:
            def __init__(self, **kwargs) -> None:
                self.kwargs = kwargs

        def fake_calculate(*args, **kwargs):
            raise ValueError("Year 2045: Cannot fill slot 'RP': need 36 eligible pitchers (IP > 0) but only found 21.")

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
                json={"teams": 12, "pit_rp": 3, "start_year": 2026},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Cannot fill slot 'RP'", response.json()["detail"])

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

    def test_points_mode_respects_custom_scoring_weights(self) -> None:
        bat_rows = [
            {
                "Player": "Dual Threat",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 28,
                "AB": 100,
                "H": 30,
                "2B": 5,
                "3B": 0,
                "HR": 10,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "dual-threat",
                "PlayerEntityKey": "dual-threat",
            }
        ]
        pit_rows = [
            {
                "Player": "Dual Threat",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "IP": 100,
                "W": 10,
                "L": 5,
                "K": 120,
                "SV": 0,
                "SVH": 0,
                "H": 80,
                "ER": 30,
                "BB": 25,
                "PlayerKey": "dual-threat",
                "PlayerEntityKey": "dual-threat",
            }
        ]

        base_payload = {
            "scoring_mode": "points",
            "start_year": 2026,
            "horizon": 1,
            "teams": 2,
            "hit_c": 0,
            "hit_1b": 0,
            "hit_2b": 0,
            "hit_3b": 0,
            "hit_ss": 0,
            "hit_ci": 0,
            "hit_mi": 0,
            "hit_of": 1,
            "hit_ut": 0,
            "pit_p": 1,
            "pit_sp": 0,
            "pit_rp": 0,
            "bench": 0,
            "minors": 0,
            "ir": 0,
            "pts_hit_1b": 0,
            "pts_hit_2b": 0,
            "pts_hit_3b": 0,
            "pts_hit_r": 0,
            "pts_hit_rbi": 0,
            "pts_hit_sb": 0,
            "pts_hit_bb": 0,
            "pts_hit_so": 0,
            "pts_pit_ip": 0,
            "pts_pit_w": 0,
            "pts_pit_l": 0,
            "pts_pit_k": 0,
            "pts_pit_sv": 0,
            "pts_pit_svh": 0,
            "pts_pit_h": 0,
            "pts_pit_er": 0,
            "pts_pit_bb": 0,
        }

        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ), patch.object(
            app_module,
            "BAT_DATA",
            bat_rows,
        ), patch.object(
            app_module,
            "PIT_DATA",
            pit_rows,
        ), patch.object(
            app_module,
            "BAT_DATA_RAW",
            bat_rows,
        ), patch.object(
            app_module,
            "PIT_DATA_RAW",
            pit_rows,
        ), patch.object(
            app_module,
            "_player_identity_by_name",
            return_value={"Dual Threat": ("dual-threat", "dual-threat")},
        ):
            low_hr = self.client.post("/api/calculate", json={**base_payload, "pts_hit_hr": 2})
            high_hr = self.client.post("/api/calculate", json={**base_payload, "pts_hit_hr": 4})

        self.assertEqual(low_hr.status_code, 200)
        self.assertEqual(high_hr.status_code, 200)
        low_raw = low_hr.json()["data"][0]["RawDynastyValue"]
        high_raw = high_hr.json()["data"][0]["RawDynastyValue"]
        self.assertEqual(low_raw, 20.0)
        self.assertEqual(high_raw, 40.0)
        self.assertGreater(high_raw, low_raw)

    def test_points_mode_applies_position_eligibility_for_year_values(self) -> None:
        bat_rows = [
            {
                "Player": "Dual Threat",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "Age": 28,
                "AB": 100,
                "H": 30,
                "2B": 5,
                "3B": 0,
                "HR": 10,
                "R": 0,
                "RBI": 0,
                "SB": 0,
                "BB": 0,
                "SO": 0,
                "PlayerKey": "dual-threat",
                "PlayerEntityKey": "dual-threat",
            }
        ]
        pit_rows = [
            {
                "Player": "Dual Threat",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "SP",
                "Age": 28,
                "IP": 100,
                "W": 10,
                "L": 5,
                "K": 120,
                "SV": 0,
                "SVH": 0,
                "H": 80,
                "ER": 30,
                "BB": 25,
                "PlayerKey": "dual-threat",
                "PlayerEntityKey": "dual-threat",
            }
        ]

        payload = {
            "scoring_mode": "points",
            "start_year": 2026,
            "horizon": 1,
            "teams": 2,
            "hit_c": 1,
            "hit_1b": 0,
            "hit_2b": 0,
            "hit_3b": 0,
            "hit_ss": 0,
            "hit_ci": 0,
            "hit_mi": 0,
            "hit_of": 0,
            "hit_ut": 0,
            "pit_p": 1,
            "pit_sp": 0,
            "pit_rp": 0,
            "bench": 0,
            "minors": 0,
            "ir": 0,
            "pts_hit_1b": 0,
            "pts_hit_2b": 0,
            "pts_hit_3b": 0,
            "pts_hit_hr": 4,
            "pts_hit_r": 0,
            "pts_hit_rbi": 0,
            "pts_hit_sb": 0,
            "pts_hit_bb": 0,
            "pts_hit_so": 0,
            "pts_pit_ip": 0,
            "pts_pit_w": 0,
            "pts_pit_l": 0,
            "pts_pit_k": 0,
            "pts_pit_sv": 0,
            "pts_pit_svh": 0,
            "pts_pit_h": 0,
            "pts_pit_er": 0,
            "pts_pit_bb": 0,
        }

        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
            app_module,
            "META",
            {"years": [2026]},
        ), patch.object(
            app_module,
            "BAT_DATA",
            bat_rows,
        ), patch.object(
            app_module,
            "PIT_DATA",
            pit_rows,
        ), patch.object(
            app_module,
            "BAT_DATA_RAW",
            bat_rows,
        ), patch.object(
            app_module,
            "PIT_DATA_RAW",
            pit_rows,
        ), patch.object(
            app_module,
            "_player_identity_by_name",
            return_value={"Dual Threat": ("dual-threat", "dual-threat")},
        ):
            response = self.client.post("/api/calculate", json=payload)

        self.assertEqual(response.status_code, 200)
        row = response.json()["data"][0]
        self.assertEqual(row["Value_2026"], 0.0)
        self.assertEqual(row["RawDynastyValue"], 0.0)

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
        self.assertEqual(guardrails.get("default_minors_slots"), app_module.COMMON_DEFAULT_MINOR_SLOTS)
        self.assertIn("default_points_scoring", guardrails)
        self.assertIn("playable_by_year", guardrails)

    def test_calculate_response_includes_explanations_payload(self) -> None:
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

        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
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
        self.assertIn("explanations", payload)
        explanation = payload["explanations"]["jane-roe"]
        self.assertEqual(explanation["player"], "Jane Roe")
        self.assertEqual(explanation["mode"], "roto")
        self.assertEqual(explanation["per_year"][0]["year"], 2026)

    def test_projection_export_csv_endpoint(self) -> None:
        sample_rows = [{"Player": "Jane Roe", "Team": "SEA", "Year": 2026, "Pos": "OF"}]
        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get("/api/projections/export/bat?format=csv&include_dynasty=false")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("content-type", ""))
        self.assertIn("Player", response.text)

    def test_calculate_export_xlsx_endpoint(self) -> None:
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

        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
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
            response = self.client.post("/api/calculate/export", json={"format": "xlsx", "include_explanations": True})

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            response.headers.get("content-type", ""),
        )
        self.assertTrue(response.content.startswith(b"PK"))

    def test_rate_limit_enforced_for_sync_calculate(self) -> None:
        with patch.object(app_module, "CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE", 1), patch.object(
            app_module,
            "_run_calculate_request",
            return_value={"total": 0, "settings": {}, "data": [], "explanations": {}},
        ):
            first = self.client.post("/api/calculate", json={})
            second = self.client.post("/api/calculate", json={})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)

    def test_active_job_cap_enforced_per_ip(self) -> None:
        queued_payload = {"total": 0, "settings": {}, "data": [], "explanations": {}}

        def never_finishes(*args, **kwargs):
            return queued_payload

        with patch.object(app_module, "CALCULATOR_MAX_ACTIVE_JOBS_PER_IP", 1), patch.object(
            app_module.CALCULATOR_JOB_EXECUTOR,
            "submit",
            return_value=None,
        ):
            first = self.client.post("/api/calculate/jobs", json={})
            second = self.client.post("/api/calculate/jobs", json={})

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 429)

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
