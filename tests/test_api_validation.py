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


class ProjectionEndpointValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

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
