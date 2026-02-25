import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

import backend.app as app_module


class ProjectionEndpointValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def setUp(self) -> None:
        app_module._cached_projection_rows.cache_clear()
        app_module._cached_all_projection_rows.cache_clear()
        app_module._projection_sortable_columns_for_dataset.cache_clear()

    def test_root_serves_built_frontend_with_injected_build_id(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-app-build"), app_module.APP_BUILD_ID)
        self.assertNotIn(app_module.INDEX_BUILD_TOKEN, response.text)
        self.assertIn(app_module.APP_BUILD_ID, response.text)
        self.assertIn('/assets/index-', response.text)

    def test_assets_endpoint_sets_immutable_cache_headers(self) -> None:
        index_response = self.client.get("/")
        self.assertEqual(index_response.status_code, 200)
        asset_match = re.search(r'/assets/[^"\']+\.js', index_response.text)
        self.assertIsNotNone(asset_match)

        asset_response = self.client.get(asset_match.group(0))
        self.assertEqual(asset_response.status_code, 200)
        self.assertEqual(
            asset_response.headers.get("cache-control"),
            "public, max-age=31536000, immutable",
        )

    def test_version_endpoint_supports_etag_conditional_requests(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            first = self.client.get("/api/version")

            self.assertEqual(first.status_code, 200)
            etag = first.headers.get("etag")
            self.assertTrue(etag)

            second = self.client.get(
                "/api/version",
                headers={"If-None-Match": etag},
            )

        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.text, "")
        self.assertEqual(second.headers.get("etag"), etag)

    def test_version_endpoint_returns_200_for_mismatched_etag(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/version",
                headers={"If-None-Match": '"stale-version"'},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("etag"))

    def test_meta_endpoint_supports_etag_conditional_requests(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            first = self.client.get("/api/meta")

            self.assertEqual(first.status_code, 200)
            etag = first.headers.get("etag")
            self.assertTrue(etag)

            second = self.client.get(
                "/api/meta",
                headers={"If-None-Match": etag},
            )

        self.assertEqual(second.status_code, 304)
        self.assertEqual(second.text, "")
        self.assertEqual(second.headers.get("etag"), etag)

    def test_meta_endpoint_returns_200_for_mismatched_etag(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/meta",
                headers={"If-None-Match": '"stale-meta"'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("etag"))

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

    def test_player_keys_filter_matches_entity_or_player_key(self) -> None:
        sample_rows = [
            {
                "Player": "Jane Roe",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "PlayerKey": "jane-roe",
                "PlayerEntityKey": "jane-roe__sea",
            },
            {
                "Player": "John Doe",
                "Team": "LAD",
                "Year": 2026,
                "Pos": "SP",
                "PlayerKey": "john-doe",
                "PlayerEntityKey": "john-doe__lad",
            },
        ]

        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/bat",
                params={"player_keys": "jane-roe__sea,john-doe", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        players = {row["Player"] for row in payload["data"]}
        self.assertSetEqual(players, {"Jane Roe", "John Doe"})

    def test_all_projections_player_keys_filter(self) -> None:
        bat_rows = [
            {
                "Player": "Dual Threat",
                "Team": "LAA",
                "Year": 2026,
                "Pos": "OF",
                "PlayerKey": "dual-threat",
                "PlayerEntityKey": "dual-threat",
                "AB": 500,
                "H": 150,
                "HR": 30,
                "R": 90,
                "RBI": 95,
                "SB": 10,
            },
            {
                "Player": "Other Bat",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "1B",
                "PlayerKey": "other-bat",
                "PlayerEntityKey": "other-bat",
            },
        ]
        pit_rows = [
            {
                "Player": "Dual Threat",
                "Team": "LAA",
                "Year": 2026,
                "Pos": "SP",
                "PlayerKey": "dual-threat",
                "PlayerEntityKey": "dual-threat",
                "IP": 120,
                "W": 10,
                "K": 130,
                "SV": 0,
            },
            {
                "Player": "Other Arm",
                "Team": "BOS",
                "Year": 2026,
                "Pos": "RP",
                "PlayerKey": "other-arm",
                "PlayerEntityKey": "other-arm",
            },
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module,
            "PIT_DATA",
            pit_rows,
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/all",
                params={"player_keys": "dual-threat", "include_dynasty": "false"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["data"][0]["Player"], "Dual Threat")

    def test_projection_export_respects_player_keys_filter(self) -> None:
        sample_rows = [
            {
                "Player": "Jane Roe",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "PlayerKey": "jane-roe",
                "PlayerEntityKey": "jane-roe",
            },
            {
                "Player": "John Doe",
                "Team": "LAD",
                "Year": 2026,
                "Pos": "SP",
                "PlayerKey": "john-doe",
                "PlayerEntityKey": "john-doe",
            },
        ]
        with patch.object(app_module, "BAT_DATA", sample_rows), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/export/bat",
                params={"format": "csv", "include_dynasty": "false", "player_keys": "john-doe"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("John Doe", response.text)
        self.assertNotIn("Jane Roe", response.text)

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

    def test_oldest_projection_date_sort_keeps_missing_dates_last(self) -> None:
        bat_rows = [
            {
                "Player": "Missing Date",
                "Team": "NYY",
                "Year": 2026,
                "Pos": "OF",
                "OldestProjectionDate": None,
            },
            {
                "Player": "Older",
                "Team": "BOS",
                "Year": 2026,
                "Pos": "OF",
                "OldestProjectionDate": "2025-12-20",
            },
            {
                "Player": "Newer",
                "Team": "SEA",
                "Year": 2026,
                "Pos": "OF",
                "OldestProjectionDate": "2026-01-05",
            },
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", []
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ):
            asc_response = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "false",
                    "sort_col": "OldestProjectionDate",
                    "sort_dir": "asc",
                },
            )
            desc_response = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "false",
                    "sort_col": "OldestProjectionDate",
                    "sort_dir": "desc",
                },
            )

        self.assertEqual(asc_response.status_code, 200)
        self.assertEqual(desc_response.status_code, 200)

        asc_players = [row["Player"] for row in asc_response.json()["data"]]
        desc_players = [row["Player"] for row in desc_response.json()["data"]]
        self.assertEqual(asc_players, ["Older", "Newer", "Missing Date"])
        self.assertEqual(desc_players, ["Newer", "Older", "Missing Date"])

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

    def test_calculator_job_overlay_reorders_dynasty_sort_globally(self) -> None:
        bat_rows = [
            {
                "Player": "Alpha",
                "Team": "NYY",
                "Year": 2026,
                "Pos": "OF",
                "DynastyValue": 1.0,
                "PlayerKey": "alpha",
                "PlayerEntityKey": "alpha",
            },
            {
                "Player": "Bravo",
                "Team": "BOS",
                "Year": 2026,
                "Pos": "OF",
                "DynastyValue": 9.0,
                "PlayerKey": "bravo",
                "PlayerEntityKey": "bravo",
            },
        ]
        overlay_job_id = "job-overlay-sort"
        overlay_job_payload = {
            "job_id": overlay_job_id,
            "status": "completed",
            "result": {
                "data": [
                    {"PlayerEntityKey": "alpha", "PlayerKey": "alpha", "DynastyValue": 20.0},
                ]
            },
        }

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", []
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE._ctx,
            "attach_dynasty_values",
            side_effect=lambda rows, _years: rows,
        ), patch.dict(
            app_module.CALCULATOR_JOBS,
            {overlay_job_id: overlay_job_payload},
            clear=True,
        ):
            baseline_response = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "true",
                    "sort_col": "DynastyValue",
                    "sort_dir": "desc",
                },
            )
            overlay_response = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "true",
                    "sort_col": "DynastyValue",
                    "sort_dir": "desc",
                    "calculator_job_id": overlay_job_id,
                },
            )

        self.assertEqual(baseline_response.status_code, 200)
        self.assertEqual(overlay_response.status_code, 200)
        baseline_players = [row["Player"] for row in baseline_response.json()["data"]]
        overlay_players = [row["Player"] for row in overlay_response.json()["data"]]
        self.assertEqual(baseline_players, ["Bravo", "Alpha"])
        self.assertEqual(overlay_players, ["Alpha", "Bravo"])
        self.assertEqual(float(overlay_response.json()["data"][0]["DynastyValue"]), 20.0)

    def test_projection_overlay_missing_job_falls_back_to_baseline_values(self) -> None:
        bat_rows = [
            {
                "Player": "Alpha",
                "Team": "NYY",
                "Year": 2026,
                "Pos": "OF",
                "DynastyValue": 1.0,
                "PlayerKey": "alpha",
                "PlayerEntityKey": "alpha",
            },
            {
                "Player": "Bravo",
                "Team": "BOS",
                "Year": 2026,
                "Pos": "OF",
                "DynastyValue": 9.0,
                "PlayerKey": "bravo",
                "PlayerEntityKey": "bravo",
            },
        ]

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", []
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE._ctx,
            "attach_dynasty_values",
            side_effect=lambda rows, _years: rows,
        ), patch.dict(
            app_module.CALCULATOR_JOBS,
            {},
            clear=True,
        ), patch.object(
            app_module,
            "_cached_calculation_job_snapshot",
            return_value=None,
        ):
            response = self.client.get(
                "/api/projections/all",
                params={
                    "include_dynasty": "true",
                    "sort_col": "DynastyValue",
                    "sort_dir": "desc",
                    "calculator_job_id": "missing-job",
                },
            )

        self.assertEqual(response.status_code, 200)
        players = [row["Player"] for row in response.json()["data"]]
        self.assertEqual(players, ["Bravo", "Alpha"])
        self.assertEqual(float(response.json()["data"][0]["DynastyValue"]), 9.0)

    def test_projection_export_uses_calculator_job_overlay_values(self) -> None:
        bat_rows = [
            {
                "Player": "Alpha",
                "Team": "NYY",
                "Year": 2026,
                "Pos": "OF",
                "DynastyValue": 1.0,
                "PlayerKey": "alpha",
                "PlayerEntityKey": "alpha",
            },
            {
                "Player": "Bravo",
                "Team": "BOS",
                "Year": 2026,
                "Pos": "OF",
                "DynastyValue": 9.0,
                "PlayerKey": "bravo",
                "PlayerEntityKey": "bravo",
            },
        ]
        overlay_job_id = "job-overlay-export"
        overlay_job_payload = {
            "job_id": overlay_job_id,
            "status": "completed",
            "result": {
                "data": [
                    {"PlayerEntityKey": "alpha", "PlayerKey": "alpha", "DynastyValue": 20.0},
                ]
            },
        }

        with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(
            app_module, "PIT_DATA", []
        ), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE._ctx,
            "attach_dynasty_values",
            side_effect=lambda rows, _years: rows,
        ), patch.dict(
            app_module.CALCULATOR_JOBS,
            {overlay_job_id: overlay_job_payload},
            clear=True,
        ):
            response = self.client.get(
                "/api/projections/export/bat",
                params={
                    "format": "csv",
                    "include_dynasty": "true",
                    "sort_col": "DynastyValue",
                    "sort_dir": "desc",
                    "calculator_job_id": overlay_job_id,
                    "columns": "Player,DynastyValue",
                },
            )

        self.assertEqual(response.status_code, 200)
        lines = response.text.splitlines()
        self.assertGreaterEqual(len(lines), 2)
        first_row = lines[1].split(",")
        self.assertEqual(first_row[0], "Alpha")
        self.assertEqual(float(first_row[1]), 20.0)

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

    def test_get_default_dynasty_lookup_prefers_precomputed_cache(self) -> None:
        precomputed = (
            {"entity-a": {"DynastyValue": 1.23, "Value_2026": 0.5}},
            {"player-a": {"DynastyValue": 1.23, "Value_2026": 0.5}},
            set(),
            ["Value_2026"],
        )

        app_module._get_default_dynasty_lookup.cache_clear()
        try:
            with patch.object(
                app_module,
                "_inspect_precomputed_default_dynasty_lookup",
                return_value=app_module.DynastyLookupCacheInspection(
                    status="ready",
                    expected_version="fresh-version",
                    found_version="fresh-version",
                    lookup=precomputed,
                ),
            ), patch.object(app_module, "_calculate_common_dynasty_frame_cached") as calculate_mock:
                actual = app_module._get_default_dynasty_lookup()
        finally:
            app_module._get_default_dynasty_lookup.cache_clear()

        self.assertEqual(actual, precomputed)
        calculate_mock.assert_not_called()

    def test_load_precomputed_dynasty_lookup_cache_validates_data_version(self) -> None:
        payload = {
            "data_version": "stale-version",
            "lookup_by_entity": {"entity-a": {"DynastyValue": 4.2}},
            "lookup_by_player_key": {"player-a": {"DynastyValue": 4.2}},
            "ambiguous_player_keys": [],
            "year_cols": ["Value_2026"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "dynasty_lookup.json"
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(app_module, "DYNASTY_LOOKUP_CACHE_PATH", cache_path), patch.object(
                app_module,
                "_current_data_version",
                return_value="fresh-version",
            ), patch.object(app_module.os, "getenv", return_value=""):
                loaded = app_module._load_precomputed_default_dynasty_lookup()

        self.assertIsNone(loaded)

    def test_load_precomputed_dynasty_lookup_prefers_cache_data_version_key(self) -> None:
        payload = {
            "cache_data_version": "fresh-version",
            "data_version": "stale-version",
            "lookup_by_entity": {"entity-a": {"DynastyValue": 4.2}},
            "lookup_by_player_key": {"player-a": {"DynastyValue": 4.2}},
            "ambiguous_player_keys": [],
            "year_cols": ["Value_2026"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "dynasty_lookup.json"
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

            with patch.object(app_module, "DYNASTY_LOOKUP_CACHE_PATH", cache_path), patch.object(
                app_module,
                "_current_data_version",
                return_value="fresh-version",
            ), patch.object(app_module.os, "getenv", return_value=""):
                loaded = app_module._load_precomputed_default_dynasty_lookup()

        self.assertIsNotNone(loaded)

    def test_compute_content_data_version_is_path_independent(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first_paths = []
            second_paths = []
            for name, content in (
                ("meta.json", b'{"years":[2026]}'),
                ("bat.json", b'[{"Player":"A","Year":2026}]'),
                ("pitch.json", b'[{"Player":"B","Year":2026}]'),
                ("Dynasty Baseball Projections.xlsx", b"fake-xlsx-bytes"),
            ):
                first_path = Path(first_dir) / name
                second_path = Path(second_dir) / name
                first_path.write_bytes(content)
                second_path.write_bytes(content)
                first_paths.append(first_path)
                second_paths.append(second_path)

            with patch.object(app_module, "BASE_DIR", Path(first_dir).parent):
                first_version = app_module._compute_content_data_version(tuple(first_paths))
            with patch.object(app_module, "BASE_DIR", Path(second_dir).parent):
                second_version = app_module._compute_content_data_version(tuple(second_paths))

        self.assertEqual(first_version, second_version)

    def test_compute_content_data_version_changes_when_file_content_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path_a = Path(tmpdir) / "a.json"
            path_b = Path(tmpdir) / "b.json"
            path_a.write_text('{"value":1}', encoding="utf-8")
            path_b.write_text('{"value":2}', encoding="utf-8")

            version_before = app_module._compute_content_data_version((path_a, path_b))
            path_b.write_text('{"value":3}', encoding="utf-8")
            version_after = app_module._compute_content_data_version((path_a, path_b))

        self.assertNotEqual(version_before, version_after)

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

    def test_projections_fail_fast_when_precomputed_lookup_is_required(self) -> None:
        app_module._get_default_dynasty_lookup.cache_clear()
        try:
            with patch.object(
                app_module,
                "REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP",
                True,
            ), patch.object(
                app_module,
                "_inspect_precomputed_default_dynasty_lookup",
                return_value=app_module.DynastyLookupCacheInspection(
                    status="missing",
                    expected_version="expected-version",
                ),
            ), patch.object(app_module, "_calculate_common_dynasty_frame_cached") as calculate_mock:
                response = self.client.get("/api/projections/all", params={"limit": 1, "offset": 0})
        finally:
            app_module._get_default_dynasty_lookup.cache_clear()

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertIn("Run `python preprocess.py`", payload.get("detail", ""))
        calculate_mock.assert_not_called()

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
        self.assertEqual(row["ProjectionsUsed"], 3)
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
        self.assertEqual(row["ProjectionsUsed"], 2)
        self.assertEqual(row["OldestProjectionDate"], "2025-12-30")


