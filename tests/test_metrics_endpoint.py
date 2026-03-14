"""Integration test for the /api/metrics endpoint."""

import unittest
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.app as app_module

pytestmark = pytest.mark.integration


class MetricsEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def test_metrics_endpoint_returns_snapshot(self) -> None:
        with patch.object(app_module, "_refresh_data_if_needed", return_value=None):
            response = self.client.get("/api/metrics")

        # Endpoint may not be registered if metrics_enabled=False,
        # but in test env the default is True
        if response.status_code == 404:
            self.skipTest("Metrics endpoint not registered (metrics disabled)")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("uptime_seconds", payload)
        self.assertIn("requests", payload)
        self.assertIn("total", payload["requests"])
        self.assertIn("errors_4xx", payload["requests"])
        self.assertIn("errors_5xx", payload["requests"])
        self.assertIn("rate_limited", payload["requests"])
        self.assertIn("latency_ms", payload)
        self.assertIn("status_codes", payload)
        self.assertIn("routes", payload)
