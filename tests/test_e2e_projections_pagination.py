import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import pytest

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    PlaywrightError = Exception  # type: ignore[assignment]
    sync_playwright = None

pytestmark = pytest.mark.e2e


class ProjectionsPaginationE2ETests(unittest.TestCase):
    """Browser-level validation of projections filter and pagination behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        if sync_playwright is None:
            raise unittest.SkipTest(
                "Playwright is not installed. Install test deps with: pip install -r requirements-dev.txt"
            )

        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.port = int(os.environ.get("FF_E2E_PORT", "8765"))
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.port),
            ],
            cwd=str(cls.repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            cls._wait_for_server()
        except Exception:
            cls._stop_server()
            raise

        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            cls.playwright.stop()
            cls._stop_server()
            message = str(exc)
            if "error while loading shared libraries" in message:
                raise unittest.SkipTest(
                    "Playwright Chromium is installed but missing OS browser libraries "
                    "(for example libnspr4.so). Install deps with sudo: "
                    "python -m playwright install-deps chromium"
                ) from exc
            raise unittest.SkipTest(
                "Playwright Chromium is not installed. Run: python -m playwright install chromium"
            ) from exc

    @classmethod
    def tearDownClass(cls) -> None:
        browser = getattr(cls, "browser", None)
        if browser is not None:
            browser.close()

        playwright = getattr(cls, "playwright", None)
        if playwright is not None:
            playwright.stop()

        cls._stop_server()

    @classmethod
    def _wait_for_server(cls, timeout_seconds: float = 30.0) -> None:
        deadline = time.time() + timeout_seconds
        url = f"{cls.base_url}/api/meta"
        last_error: Exception | None = None

        while time.time() < deadline:
            if cls.server.poll() is not None:
                raise RuntimeError("uvicorn exited before becoming ready")
            try:
                with urlopen(url, timeout=1.5) as response:
                    if 200 <= response.status < 300:
                        return
            except Exception as exc:  # pragma: no cover - timing dependent
                last_error = exc
                time.sleep(0.2)

        raise TimeoutError(f"Timed out waiting for server at {url}") from last_error

    @classmethod
    def _stop_server(cls) -> None:
        server = getattr(cls, "server", None)
        if server is None:
            return
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)

    def test_invalid_empty_year_selection_falls_back_to_career_totals(self) -> None:
        page = self.browser.new_page()
        try:
            projection_request_urls: list[str] = []
            career_totals_value = "__career_totals__"

            def on_request(request) -> None:
                if "/api/projections/all" in request.url:
                    projection_request_urls.append(request.url)

            page.on("request", on_request)
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)

            page.wait_for_function(
                """
                () => {
                  const yearSelect = document.getElementById('projections-year-filter');
                  if (!yearSelect) return false;
                  if (yearSelect.value !== '__career_totals__') return false;
                  const el = document.querySelector('.filter-bar .result-count');
                  if (!el) return false;
                  const match = (el.textContent || '').match(/[\\d,]+/);
                  if (!match) return false;
                  const value = parseInt(match[0].replaceAll(',', ''), 10);
                  return Number.isFinite(value) && value > 100;
                }
                """,
                timeout=90000,
            )

            count_text = page.locator(".filter-bar .result-count").first.inner_text()
            match = re.search(r"[\d,]+", count_text)
            self.assertIsNotNone(match, f"Expected numeric row count in text: {count_text!r}")
            loaded_count = int(match.group(0).replace(",", ""))
            self.assertGreater(loaded_count, 100, f"Expected at least 100 rows, got {loaded_count}")

            offsets_seen = set()
            career_totals_requests = 0
            for url in projection_request_urls:
                parsed = urlparse(url)
                query = parse_qs(parsed.query)
                offset = query.get("offset", [None])[0]
                if offset is not None:
                    offsets_seen.add(offset)
                if query.get("career_totals", [None])[0] == "true":
                    career_totals_requests += 1

            self.assertIn("0", offsets_seen)
            self.assertTrue(
                any(offset != "0" for offset in offsets_seen),
                f"Expected paginated projections requests, got offsets: {sorted(offsets_seen)}",
            )
            self.assertTrue(offsets_seen, "Expected at least one projections request with an offset query param")
            self.assertGreater(career_totals_requests, 0, "Expected at least one career_totals=true projections request")

            page.evaluate(
                """
                () => {
                  const yearSelect = document.getElementById("projections-year-filter");
                  if (!yearSelect) throw new Error("Projection year filter is missing");
                  yearSelect.value = "";
                  yearSelect.dispatchEvent(new Event("change", { bubbles: true }));
                }
                """
            )
            page.wait_for_function(
                """
                (expectedValue) => {
                  const yearSelect = document.getElementById('projections-year-filter');
                  return !!yearSelect && yearSelect.value === expectedValue;
                }
                """,
                career_totals_value,
                timeout=10000,
            )

            fallback_count_text = page.locator(".filter-bar .result-count").first.inner_text()
            fallback_match = re.search(r"[\d,]+", fallback_count_text)
            self.assertIsNotNone(
                fallback_match,
                f"Expected numeric row count after invalid empty year selection: {fallback_count_text!r}",
            )
            fallback_count = int(fallback_match.group(0).replace(",", ""))
            self.assertEqual(
                fallback_count,
                loaded_count,
                "Invalid empty year selection should not switch away from career totals mode",
            )
        finally:
            page.close()

    def test_calculator_shows_backend_422_detail_message(self) -> None:
        page = self.browser.new_page()
        try:
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
            page.get_by_role("button", name="Dynasty Calculator").click()

            page.route(
                "**/api/calculate/jobs",
                lambda route: route.fulfill(
                    status=422,
                    content_type="application/json",
                    body=json.dumps({"detail": "Not enough players for selected settings."}),
                ),
            )

            page.locator(".calc-btn").first.click()
            page.wait_for_function(
                """
                () => {
                  const el = document.querySelector('.calc-status');
                  return !!el && (el.textContent || '').includes('Not enough players for selected settings.');
                }
                """,
                timeout=10000,
            )

            status_text = page.locator(".calc-status").first.inner_text()
            self.assertIn("Not enough players for selected settings.", status_text)
        finally:
            page.close()

    def test_calculator_shows_non_json_error_body_text(self) -> None:
        page = self.browser.new_page()
        try:
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
            page.get_by_role("button", name="Dynasty Calculator").click()

            page.route(
                "**/api/calculate/jobs",
                lambda route: route.fulfill(
                    status=500,
                    content_type="text/plain",
                    body="Gateway timeout while waiting for calculation worker.",
                ),
            )

            page.locator(".calc-btn").first.click()
            page.wait_for_function(
                """
                () => {
                  const el = document.querySelector('.calc-status');
                  return !!el && (el.textContent || '').includes('Gateway timeout while waiting for calculation worker.');
                }
                """,
                timeout=10000,
            )

            status_text = page.locator(".calc-status").first.inner_text()
            self.assertIn("Gateway timeout while waiting for calculation worker.", status_text)
            self.assertNotIn("[object Object]", status_text)
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
