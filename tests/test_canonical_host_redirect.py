import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.api.app_factory import create_app


def _build_test_app(canonical_host: str):
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
        canonical_host=canonical_host,
        enable_startup_calc_prewarm=False,
        prewarm_default_calculation_caches=lambda: None,
        calculator_job_executor=ThreadPoolExecutor(max_workers=1),
    )

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


class CanonicalHostRedirectTests(unittest.TestCase):
    def test_redirects_www_host_to_canonical_host(self) -> None:
        app = _build_test_app("fantasy-foundry.com")
        with TestClient(app) as client:
            response = client.get(
                "http://www.fantasy-foundry.com/ping?view=full",
                headers={"host": "www.fantasy-foundry.com"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 308)
        self.assertEqual(response.headers.get("location"), "http://fantasy-foundry.com/ping?view=full")

    def test_redirect_uses_forwarded_host_and_proto(self) -> None:
        app = _build_test_app("fantasy-foundry.com")
        with TestClient(app) as client:
            response = client.get(
                "/ping?view=full",
                headers={
                    "host": "railway-internal",
                    "x-forwarded-host": "www.fantasy-foundry.com:443",
                    "x-forwarded-proto": "https",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 308)
        self.assertEqual(response.headers.get("location"), "https://fantasy-foundry.com/ping?view=full")

    def test_redirect_is_disabled_without_canonical_host(self) -> None:
        app = _build_test_app("")
        with TestClient(app) as client:
            response = client.get("/ping", headers={"host": "www.fantasy-foundry.com"}, follow_redirects=False)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
