import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app as app_module


class OperationalHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def setUp(self) -> None:
        with app_module.REQUEST_RATE_LIMIT_LOCK:
            app_module.REQUEST_RATE_LIMIT_BUCKETS.clear()
            app_module._REQUEST_RATE_LIMIT_LAST_SWEEP_TS = 0.0

    def test_projection_read_rate_limit_returns_retry_after_header(self) -> None:
        with patch.object(app_module.PROJECTION_SERVICE._ctx.rate_limits, "read_per_minute", 1), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE,
            "projection_response",
            return_value={"total": 0, "offset": 0, "limit": 200, "data": []},
        ):
            first = self.client.get("/api/projections/bat", params={"include_dynasty": "false"})
            second = self.client.get("/api/projections/bat", params={"include_dynasty": "false"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.headers.get("retry-after"), "60")

    def test_projection_export_rate_limit_returns_retry_after_header(self) -> None:
        with patch.object(app_module.PROJECTION_SERVICE._ctx.rate_limits, "export_per_minute", 1), patch.object(
            app_module,
            "_refresh_data_if_needed",
            return_value=None,
        ), patch.object(
            app_module.PROJECTION_SERVICE,
            "export_projections",
            return_value={"ok": True},
        ):
            first = self.client.get("/api/projections/export/bat", params={"format": "csv", "include_dynasty": "false"})
            second = self.client.get("/api/projections/export/bat", params={"format": "csv", "include_dynasty": "false"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.headers.get("retry-after"), "60")

    def test_request_id_header_is_echoed_when_provided(self) -> None:
        response = self.client.get("/api/health", headers={"X-Request-Id": "req-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-request-id"), "req-123")

    def test_ops_endpoint_returns_operational_payload(self) -> None:
        response = self.client.get("/api/ops")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertIn("build", payload)
        self.assertIn("data", payload)
        self.assertIn("runtime", payload)
        self.assertIn("rate_limits", payload)
        self.assertIn("queues", payload)

    def test_validate_runtime_configuration_rejects_production_wildcard_cors(self) -> None:
        with patch.object(app_module, "APP_ENVIRONMENT", "production"), patch.object(
            app_module,
            "CORS_ALLOW_ORIGINS",
            ("*",),
        ), patch.object(
            app_module,
            "TRUST_X_FORWARDED_FOR",
            False,
        ), patch.object(
            app_module,
            "TRUSTED_PROXY_NETWORKS",
            (),
        ), patch.object(
            app_module,
            "REQUIRE_CALCULATE_AUTH",
            False,
        ), patch.object(
            app_module,
            "CALCULATE_API_KEY_IDENTITIES",
            {},
        ):
            with self.assertRaisesRegex(RuntimeError, "FF_CORS_ALLOW_ORIGINS"):
                app_module._validate_runtime_configuration()

    def test_validate_runtime_configuration_rejects_xff_without_trusted_proxy_cidrs(self) -> None:
        with patch.object(app_module, "APP_ENVIRONMENT", "production"), patch.object(
            app_module,
            "CORS_ALLOW_ORIGINS",
            ("https://fantasy-foundry.com",),
        ), patch.object(
            app_module,
            "TRUST_X_FORWARDED_FOR",
            True,
        ), patch.object(
            app_module,
            "TRUSTED_PROXY_NETWORKS",
            (),
        ), patch.object(
            app_module,
            "REQUIRE_CALCULATE_AUTH",
            False,
        ), patch.object(
            app_module,
            "CALCULATE_API_KEY_IDENTITIES",
            {},
        ):
            with self.assertRaisesRegex(RuntimeError, "FF_TRUST_X_FORWARDED_FOR"):
                app_module._validate_runtime_configuration()

    def test_validate_runtime_configuration_rejects_auth_without_keys(self) -> None:
        with patch.object(app_module, "APP_ENVIRONMENT", "production"), patch.object(
            app_module,
            "CORS_ALLOW_ORIGINS",
            ("https://fantasy-foundry.com",),
        ), patch.object(
            app_module,
            "TRUST_X_FORWARDED_FOR",
            False,
        ), patch.object(
            app_module,
            "TRUSTED_PROXY_NETWORKS",
            (),
        ), patch.object(
            app_module,
            "REQUIRE_CALCULATE_AUTH",
            True,
        ), patch.object(
            app_module,
            "CALCULATE_API_KEY_IDENTITIES",
            {},
        ):
            with self.assertRaisesRegex(RuntimeError, "FF_REQUIRE_CALCULATE_AUTH"):
                app_module._validate_runtime_configuration()


if __name__ == "__main__":
    unittest.main()
