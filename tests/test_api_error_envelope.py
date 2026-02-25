import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.app as app_module


class ApiErrorEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def test_validation_error_uses_standard_envelope(self) -> None:
        response = self.client.get("/api/projections/bat", params={"limit": 0})

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload.get("error_code"), "validation_error")
        self.assertTrue(payload.get("message"))
        self.assertTrue(payload.get("request_id"))
        self.assertIsInstance(payload.get("detail"), list)
        self.assertEqual(response.headers.get("x-request-id"), payload.get("request_id"))

    def test_error_envelope_preserves_supplied_request_id(self) -> None:
        response = self.client.get(
            "/api/projections/bat",
            params={"limit": 0},
            headers={"X-Request-Id": "req-provided-1"},
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload.get("request_id"), "req-provided-1")
        self.assertEqual(response.headers.get("x-request-id"), "req-provided-1")

    def test_http_exception_uses_standard_envelope(self) -> None:
        response = self.client.get(
            "/api/projections/bat",
            params={"sort_col": "no_such_column", "include_dynasty": "false"},
        )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload.get("error_code"), "validation_error")
        self.assertIn("sort_col", str(payload.get("detail")))
        self.assertEqual(payload.get("message"), str(payload.get("detail")))

    def test_unhandled_exception_returns_internal_error_envelope(self) -> None:
        non_raising_client = TestClient(app_module.app, raise_server_exceptions=False)
        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
            app_module.PROJECTION_SERVICE,
            "projection_response",
            side_effect=RuntimeError("boom"),
        ):
            response = non_raising_client.get("/api/projections/bat", params={"include_dynasty": "false"})

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertEqual(payload.get("error_code"), "internal_error")
        self.assertEqual(payload.get("message"), "Internal server error.")
        self.assertEqual(payload.get("detail"), "Internal server error.")
        self.assertTrue(payload.get("request_id"))

    def test_ready_returns_503_when_calculation_worker_is_unavailable(self) -> None:
        with patch.object(app_module, "_refresh_data_if_needed", return_value=None), patch.object(
            app_module, "INDEX_PATH"
        ) as index_path_mock, patch.object(app_module, "_inspect_precomputed_default_dynasty_lookup") as lookup_mock, patch.object(
            app_module,
            "CALCULATOR_JOB_EXECUTOR",
            types.SimpleNamespace(_shutdown=True),
        ):
            index_path_mock.exists.return_value = True
            lookup_mock.return_value = app_module.DynastyLookupCacheInspection(
                status="ready",
                expected_version="test-version",
                found_version="test-version",
            )
            response = self.client.get("/api/ready")

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload.get("error_code"), "service_unavailable")
        self.assertIn("Calculation worker is unavailable", str(payload.get("message")))
        self.assertTrue(payload.get("request_id"))
