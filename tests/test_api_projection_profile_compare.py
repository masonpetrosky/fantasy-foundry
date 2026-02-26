import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app as app_module


class ProjectionProfileCompareApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def test_profile_endpoint_returns_service_payload(self) -> None:
        expected = {
            "player_id": "jane-roe",
            "dataset": "all",
            "include_dynasty": True,
            "series_total": 1,
            "career_totals_total": 1,
            "matched_players": [
                {
                    "player_entity_key": "jane-roe",
                    "player_key": None,
                    "player": None,
                    "team": None,
                    "pos": None,
                }
            ],
            "series": [{"Player": "Jane Roe", "Year": 2026}],
            "career_totals": [{"Player": "Jane Roe", "DynastyValue": 10.0}],
        }
        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
            app_module.PROJECTION_SERVICE,
            "projection_profile",
            return_value=expected,
        ) as mocked:
            response = self.client.get(
                "/api/projections/profile/jane-roe",
                params={"dataset": "all", "include_dynasty": "true"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        mocked.assert_called_once_with(
            player_id="jane-roe",
            dataset="all",
            include_dynasty=True,
            calculator_job_id=None,
        )

    def test_compare_endpoint_returns_service_payload(self) -> None:
        expected = {
            "dataset": "all",
            "requested_player_keys": ["jane-roe", "john-roe"],
            "matched_player_keys": ["jane-roe", "john-roe"],
            "career_totals": False,
            "include_dynasty": True,
            "total": 2,
            "data": [
                {"Player": "Jane Roe", "DynastyValue": 10.0},
                {"Player": "John Roe", "DynastyValue": 9.5},
            ],
        }
        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
            app_module.PROJECTION_SERVICE,
            "projection_compare",
            return_value=expected,
        ) as mocked:
            response = self.client.get(
                "/api/projections/compare",
                params={
                    "player_keys": "jane-roe,john-roe",
                    "dataset": "all",
                    "career_totals": "false",
                    "year": "2027",
                    "dynasty_years": "2027",
                    "include_dynasty": "true",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        mocked.assert_called_once_with(
            player_keys="jane-roe,john-roe",
            dataset="all",
            include_dynasty=True,
            calculator_job_id=None,
            career_totals=False,
            year=2027,
            years=None,
            dynasty_years="2027",
        )


if __name__ == "__main__":
    unittest.main()
