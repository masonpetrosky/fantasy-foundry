import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.api.app_factory import create_app


def _build_test_app():
    app = create_app(
        title="test",
        version="0.0.0",
        app_build_id="test-build",
        api_no_cache_headers={},
        cors_allow_origins=("*",),
        environment="development",
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

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


class HeadRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_test_app()
        self.client = TestClient(self.app)

    def test_head_returns_200_with_empty_body(self) -> None:
        response = self.client.head("/ping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_head_preserves_headers_from_get(self) -> None:
        get_response = self.client.get("/ping")
        head_response = self.client.head("/ping")
        self.assertEqual(head_response.status_code, get_response.status_code)
        self.assertEqual(
            head_response.headers.get("content-type"),
            get_response.headers.get("content-type"),
        )

    def test_head_on_api_health(self) -> None:
        response = self.client.head("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_head_includes_security_headers(self) -> None:
        response = self.client.head("/ping")
        self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")

    def test_head_on_nonexistent_route_returns_404(self) -> None:
        response = self.client.head("/no-such-route")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, b"")

    def test_get_still_works_normally(self) -> None:
        response = self.client.get("/ping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_head_content_length_is_zero(self) -> None:
        """HEAD response must not carry the GET Content-Length (Uvicorn enforces match)."""
        response = self.client.head("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers.get("content-length"), "0")

    def test_head_strips_content_encoding(self) -> None:
        """Content-Encoding from a compressed GET must not leak into HEAD."""
        response = self.client.head("/api/health")
        self.assertIsNone(response.headers.get("content-encoding"))
