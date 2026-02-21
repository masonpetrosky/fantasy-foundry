import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.api.app_factory import create_app


def _build_test_app(*, environment: str):
    app = create_app(
        title="test",
        version="0.0.0",
        app_build_id="test-build",
        api_no_cache_headers={},
        cors_allow_origins=("*",),
        environment=environment,
        refresh_data_if_needed=lambda: None,
        current_data_version=lambda: "test-data",
        client_identity_resolver=lambda _request: "test-client",
        canonical_host="",
        enable_startup_calc_prewarm=False,
        prewarm_default_calculation_caches=lambda: None,
        calculator_job_executor=ThreadPoolExecutor(max_workers=1),
    )

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


class SecurityHeaderTests(unittest.TestCase):
    def test_security_headers_are_attached_by_default(self) -> None:
        app = _build_test_app(environment="development")
        with TestClient(app) as client:
            response = client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")
        self.assertEqual(response.headers.get("referrer-policy"), "strict-origin-when-cross-origin")
        self.assertEqual(
            response.headers.get("permissions-policy"),
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        self.assertIn("default-src 'self'", str(response.headers.get("content-security-policy") or ""))
        self.assertIsNone(response.headers.get("strict-transport-security"))

    def test_hsts_only_applies_for_production_https_requests(self) -> None:
        app = _build_test_app(environment="production")
        with TestClient(app) as client:
            https_response = client.get("/ping", headers={"x-forwarded-proto": "https"})
            http_response = client.get("/ping", headers={"x-forwarded-proto": "http"})

        self.assertEqual(
            https_response.headers.get("strict-transport-security"),
            "max-age=31536000; includeSubDomains; preload",
        )
        self.assertIsNone(http_response.headers.get("strict-transport-security"))
