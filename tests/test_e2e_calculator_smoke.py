import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

import pytest

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    PlaywrightError = Exception  # type: ignore[assignment]
    sync_playwright = None

pytestmark = pytest.mark.e2e


class CalculatorSmokeE2ETests(unittest.TestCase):
    """Lightweight browser smoke coverage for calculator UX on desktop + mobile."""

    @classmethod
    def setUpClass(cls) -> None:
        if sync_playwright is None:
            raise unittest.SkipTest(
                "Playwright is not installed. Install test deps with: pip install -r requirements-dev.txt"
            )

        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.port = int(os.environ.get("FF_E2E_CALC_SMOKE_PORT", "8766"))
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

    def _open_calculator(self, page) -> None:
        page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
        page.get_by_role("button", name="Dynasty Calculator").click()
        page.wait_for_selector(".calc-sidebar", timeout=20000)

    def _switch_to_points_mode(self, page) -> None:
        setup_group = page.locator(".calc-sidebar .form-group").filter(
            has=page.locator("label", has_text="Setup")
        ).first
        setup_group.locator("select").first.select_option("points")
        sims_input = page.locator(".calc-sidebar .form-group").filter(
            has=page.locator("label", has_text="Simulations")
        ).first.locator("input").first
        self.assertTrue(sims_input.is_disabled(), "Expected simulations input to be disabled in points mode")

    def _run_calculation_and_wait(self, page) -> None:
        page.locator(".calc-btn").first.click()
        page.wait_for_function(
            """
            () => {
              const status = document.querySelector('.calc-status');
              if (!status) return false;
              const text = (status.textContent || '').trim();
              return text.includes('Done -') || text.includes('Done –');
            }
            """,
            timeout=180000,
        )
        page.wait_for_selector(".calc-results-toolbar", timeout=30000)
        page.wait_for_selector(".rankings-table tbody tr.clickable-row", timeout=30000)

    def _assert_result_count_format(self, page) -> None:
        count_text = page.locator(".calc-results-toolbar .result-count").first.inner_text().strip()
        match = re.search(r"([\d,]+)\s*/\s*([\d,]+)\s+players", count_text)
        self.assertIsNotNone(match, f"Expected 'filtered / total players' text format, got {count_text!r}")
        filtered_count = int(match.group(1).replace(",", ""))
        total_count = int(match.group(2).replace(",", ""))
        self.assertGreater(total_count, 0, "Expected at least one ranked player")
        self.assertGreaterEqual(total_count, filtered_count, "Expected filtered count to be <= total count")

    def _open_columns_menu(self, page, force: bool = False):
        columns_button = page.locator("button.inline-btn").filter(has_text="Columns (").first
        columns_button.scroll_into_view_if_needed()
        columns_button.click(force=force)
        page.wait_for_selector(".multi-select-menu", timeout=5000)
        return columns_button

    def test_desktop_calculator_polish_smoke(self) -> None:
        context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        try:
            self._open_calculator(page)
            self._switch_to_points_mode(page)
            self._run_calculation_and_wait(page)
            self._assert_result_count_format(page)

            search_input = page.locator(".calc-results-toolbar input[type='text']").first
            search_input.fill("shohei")
            page.wait_for_timeout(250)

            reset_filters_btn = page.get_by_role("button", name="Reset Filters")
            self.assertTrue(reset_filters_btn.is_enabled(), "Expected Reset Filters button to enable after typing")
            reset_filters_btn.click()
            self.assertEqual(search_input.input_value(), "")

            columns_button = self._open_columns_menu(page)
            optional_col_inputs = page.locator(
                ".multi-select-menu .multi-select-option input[type='checkbox']:not([disabled])"
            )
            self.assertGreater(optional_col_inputs.count(), 0, "Expected at least one optional column toggle")
            optional_col_inputs.first.uncheck()

            show_all_btn = page.get_by_role("button", name="Show All Optional Columns")
            self.assertTrue(show_all_btn.is_enabled(), "Expected show-all button enabled after hiding a column")
            show_all_btn.click()
            columns_button.click()

            columns_text = columns_button.inner_text().strip()
            self.assertRegex(columns_text, r"^Columns \(\d+/\d+\)$")

            first_row = page.locator(".rankings-table tbody tr.clickable-row").first
            first_row.click()
            page.wait_for_selector(".explain-card", timeout=10000)
            first_row.focus()
            first_row.press("Enter")
            explain_title = page.locator(".explain-card h4").first.inner_text().strip()
            self.assertIn("Value Breakdown:", explain_title)
        finally:
            context.close()

    def test_mobile_calculator_polish_smoke(self) -> None:
        context = self.browser.new_context(**self.playwright.devices["iPhone 13"])
        page = context.new_page()
        try:
            self._open_calculator(page)
            self._switch_to_points_mode(page)
            self._run_calculation_and_wait(page)
            self._assert_result_count_format(page)

            toolbar = page.locator(".calc-results-toolbar").first
            toolbar.scroll_into_view_if_needed()
            self.assertTrue(toolbar.is_visible())

            viewport_width = int(page.evaluate("window.innerWidth"))
            toolbar_width = float(
                page.evaluate(
                    "() => document.querySelector('.calc-results-toolbar').getBoundingClientRect().width"
                )
            )
            self.assertLessEqual(round(toolbar_width), viewport_width)

            self._open_columns_menu(page, force=True)
            self.assertTrue(page.locator(".multi-select-menu").first.is_visible())

            first_row = page.locator(".rankings-table tbody tr.clickable-row").first
            first_row.scroll_into_view_if_needed()
            first_row.click(force=True)
            page.wait_for_selector(".explain-card", timeout=10000)

            hint_text = page.locator(".calc-results-hint").first.inner_text().strip()
            self.assertIn("Click or press Enter", hint_text)
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
