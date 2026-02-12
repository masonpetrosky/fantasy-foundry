import unittest
from unittest.mock import patch

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

    def test_mode_must_be_common(self) -> None:
        response = self.client.post("/api/calculate", json={"mode": "league"})
        self.assertEqual(response.status_code, 422)

    def test_rejects_invalid_ip_bounds(self) -> None:
        response = self.client.post("/api/calculate", json={"ip_min": 1200, "ip_max": 1000})
        self.assertEqual(response.status_code, 422)

    def test_rejects_unknown_start_year(self) -> None:
        with patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(app_module, "META", {"years": [2026, 2027, 2028]}):
            response = self.client.post("/api/calculate", json={"start_year": 2031})

        self.assertEqual(response.status_code, 422)
        self.assertIn("start_year", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
