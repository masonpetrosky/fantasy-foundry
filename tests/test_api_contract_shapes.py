import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app as app_module


class ApiContractShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def test_version_endpoint_contract_shape(self) -> None:
        with patch.object(app_module, "_refresh_data_if_needed", return_value=None):
            response = self.client.get("/api/version")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("build_id", payload)
        self.assertIn("commit_sha", payload)
        self.assertIn("built_at", payload)
        self.assertIn("data_version", payload)
        self.assertIn("projection_freshness", payload)
        self.assertIsInstance(payload["projection_freshness"], dict)

    def test_health_endpoint_contract_shape(self) -> None:
        with patch.object(app_module, "_refresh_data_if_needed", return_value=None):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertIn("build_id", payload)
        self.assertIn("projection_rows", payload)
        self.assertIn("jobs", payload)
        self.assertIn("dynasty_lookup_cache", payload)
        self.assertIn("result_cache", payload)
        self.assertIn("calculator_prewarm", payload)
        self.assertIn("timestamp", payload)
        self.assertIsInstance(payload.get("projection_rows"), dict)
        self.assertIsInstance(payload.get("jobs"), dict)
        self.assertIsInstance(payload.get("dynasty_lookup_cache"), dict)

    def test_projections_endpoint_contract_shape(self) -> None:
        response = self.client.get("/api/projections/all", params={"limit": 2, "offset": 0})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("total", payload)
        self.assertIn("offset", payload)
        self.assertIn("limit", payload)
        self.assertIn("data", payload)
        self.assertEqual(payload.get("offset"), 0)
        self.assertEqual(payload.get("limit"), 2)
        self.assertIsInstance(payload.get("data"), list)

        if payload["data"]:
            row = payload["data"][0]
            self.assertIn("Player", row)
            self.assertIn("Team", row)
            self.assertIn("Pos", row)
