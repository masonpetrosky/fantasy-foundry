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

    def _ensure_calculator_open(self, page) -> None:
        toggle = page.locator(".embedded-calculator-toggle").first
        toggle.wait_for(state="visible", timeout=20000)
        if toggle.get_attribute("aria-expanded") != "true":
            toggle.click()
        page.wait_for_selector(".calc-sidebar", state="visible", timeout=20000)

    def _open_calculator(self, page) -> None:
        page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
        self._ensure_calculator_open(page)

    def _click_apply_to_main_table(self, page) -> None:
        run_button = page.locator(".calc-btn").first
        run_button.wait_for(state="visible", timeout=30000)
        page.wait_for_function(
            """
            () => {
              const btn = document.querySelector('.calc-btn');
              return Boolean(btn && !btn.disabled);
            }
            """,
            timeout=30000,
        )
        run_button.evaluate(
            """
            (el) => el.scrollIntoView({ block: 'center', inline: 'nearest' })
            """
        )
        try:
            run_button.click(timeout=5000)
        except PlaywrightError:
            run_button.click(force=True, timeout=10000)

    def _wait_for_run_start_signal(self, page, timeout_ms: int = 25000) -> None:
        page.wait_for_function(
            """
            () => {
              const status = document.querySelector('.calc-status');
              const text = (status?.textContent || '').trim();
              return (
                text.includes('Submitting simulation') ||
                text.includes('Running simulations') ||
                /^Applied\\s+[\\d,]+\\s+players\\s+to\\s+the\\s+table\\.$/.test(text) ||
                text.startsWith('Error:')
              );
            }
            """,
            timeout=timeout_ms,
        )

    def _start_calculation_with_retry(self, page) -> None:
        self._click_apply_to_main_table(page)
        try:
            self._wait_for_run_start_signal(page)
        except PlaywrightError:
            # Mobile viewport interactions can occasionally miss the first click when fixed CTA overlays animate.
            self._click_apply_to_main_table(page)
            self._wait_for_run_start_signal(page)

    def _wait_for_calculation_completion_signal(self, page) -> None:
        page.wait_for_function(
            """
            () => {
              const status = document.querySelector('.calc-status');
              const text = (status?.textContent || '').trim();
              const isTerminalStatus =
                /^Applied\\s+[\\d,]+\\s+players\\s+to\\s+the\\s+table\\.$/.test(text) ||
                text.startsWith('Error:');
              if (isTerminalStatus) return true;
              const hasOverlay = Boolean(document.querySelector('.projections-overlay-message'));
              const hasRows = Boolean(
                document.querySelector('.projections-table tbody tr') ||
                document.querySelector('.projection-card-list .projection-card')
              );
              return hasOverlay && hasRows;
            }
            """,
            timeout=300000,
        )

    def _assert_calculation_status_not_error(self, page) -> None:
        status_text = page.locator(".calc-status").first.inner_text().strip()
        self.assertFalse(status_text.startswith("Error:"), f"Calculator run failed: {status_text}")

    def _wait_for_projection_results_visible(self, page) -> None:
        page.wait_for_selector(".projections-overlay-message", state="attached", timeout=60000)
        page.wait_for_function(
            """
            () => Boolean(
              document.querySelector('.projections-table tbody tr') ||
              document.querySelector('.projection-card-list .projection-card')
            )
            """,
            timeout=60000,
        )

    def _switch_to_points_mode(self, page) -> None:
        setup_group = page.locator(".calc-sidebar .form-group").filter(
            has=page.locator("label", has_text="Setup")
        ).first
        setup_group.locator("select").first.select_option("points")
        sims_input = page.locator(".calc-sidebar .form-group").filter(
            has=page.locator("label", has_text="Simulations")
        ).first.locator("input").first
        self.assertTrue(sims_input.is_disabled(), "Expected simulations input to be disabled in points mode")

    def _assert_preset_save_and_select_load_flow(self, page) -> None:
        teams_input = page.locator(".calc-sidebar .form-group").filter(
            has=page.locator("label", has_text="Teams")
        ).first.locator("input").first
        teams_input.fill("14")

        preset_name = "Smoke Preset"
        preset_name_input = page.locator(".calc-sidebar .form-group").filter(
            has=page.locator("label", has_text="Preset Name")
        ).first.locator("input").first
        preset_name_input.fill(preset_name)

        save_button = page.locator(".calc-sidebar button").filter(
            has_text="Save / Update Preset"
        ).first
        self.assertTrue(save_button.is_enabled(), "Expected save button enabled after naming a preset")
        save_button.click()

        preset_status = page.locator(".calc-preset-status").first
        self.assertIn("Saved new preset", preset_status.inner_text())

        saved_presets_select = page.locator(".calc-sidebar .form-group").filter(
            has=page.locator("label", has_text="Saved Presets")
        ).first.locator("select").first
        saved_presets_select.select_option("")

        teams_input.fill("10")
        saved_presets_select.select_option(preset_name)
        page.wait_for_timeout(200)

        self.assertEqual(teams_input.input_value().strip(), "14")
        self.assertIn("Loaded preset", preset_status.inner_text())

    def _run_calculation_and_wait(self, page) -> None:
        self._start_calculation_with_retry(page)
        self._wait_for_calculation_completion_signal(page)
        self._assert_calculation_status_not_error(page)
        self._wait_for_projection_results_visible(page)

    def _set_projection_layout(self, page, mode: str) -> None:
        desired = "cards" if str(mode).strip().lower() == "cards" else "table"
        label = "Cards" if desired == "cards" else "Table"
        button = page.locator(".projection-view-toggle .projection-view-btn").filter(
            has_text=re.compile(rf"^{label}$")
        ).first
        button.scroll_into_view_if_needed()
        if button.get_attribute("aria-pressed") != "true":
            button.click(force=True)

        page.wait_for_function(
            """
            (targetMode) => {
              const active = document.querySelector('.projection-view-toggle .projection-view-btn.active');
              if (!active) return false;
              const text = (active.textContent || '').trim().toLowerCase();
              return text === targetMode;
            }
            """,
            arg=desired,
            timeout=10000,
        )

        if desired == "cards":
            page.wait_for_selector(".projection-card-list .projection-card", timeout=30000)
        else:
            page.wait_for_selector(".projections-table tbody tr", timeout=30000)

    def _assert_result_count_format(self, page) -> None:
        count_text = page.locator(".filter-bar .result-count").first.inner_text().strip()
        match = re.search(r"([\d,]+)\s+rows", count_text)
        self.assertIsNotNone(match, f"Expected row count text format, got {count_text!r}")
        total_count = int(match.group(1).replace(",", ""))
        self.assertGreater(total_count, 0, "Expected at least one projection row")

    def _open_columns_menu(self, page, force: bool = False, button_text: str = "Table Columns"):
        columns_button = page.locator("button").filter(
            has_text=re.compile(rf"^{re.escape(button_text)}")
        ).first
        menu_container = columns_button.locator(
            "xpath=ancestor::div[contains(@class, 'multi-select')]"
        ).first

        for _ in range(2):
            columns_button.scroll_into_view_if_needed()
            if columns_button.get_attribute("aria-expanded") != "true":
                columns_button.click(force=force)
            try:
                menu_container.locator(".multi-select-menu").first.wait_for(state="visible", timeout=5000)
                return columns_button
            except PlaywrightError:
                if columns_button.get_attribute("aria-expanded") == "true":
                    columns_button.click(force=True)
                page.wait_for_timeout(200)

        menu_container.locator(".multi-select-menu").first.wait_for(state="visible", timeout=5000)
        return columns_button

    def test_desktop_calculator_polish_smoke(self) -> None:
        context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        try:
            self._open_calculator(page)
            self._assert_preset_save_and_select_load_flow(page)
            self._switch_to_points_mode(page)
            self._run_calculation_and_wait(page)
            self._assert_result_count_format(page)

            overlay_text = page.locator(".projections-overlay-message").first.inner_text().strip()
            self.assertIn("calculator-adjusted dynasty values", overlay_text.lower())

            search_input = page.locator("#projections-search").first
            search_input.fill("shohei")
            page.wait_for_timeout(250)
            self.assertEqual(search_input.input_value().lower(), "shohei")

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
            self.assertRegex(columns_text, r"^Table Columns \(\d+/\d+\)$")

            first_row = page.locator(".projections-table tbody tr").first
            first_row.scroll_into_view_if_needed()
            track_button = first_row.locator("button.inline-btn").filter(has_text=re.compile("Track|Tracked")).first
            self.assertTrue(track_button.is_visible())
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

            toolbar = page.locator(".filter-bar").first
            toolbar.scroll_into_view_if_needed()
            self.assertTrue(toolbar.is_visible())

            viewport_width = int(page.evaluate("window.innerWidth"))
            toolbar_width = float(
                page.evaluate(
                    "() => document.querySelector('.filter-bar').getBoundingClientRect().width"
                )
            )
            self.assertLessEqual(round(toolbar_width), viewport_width)

            self._set_projection_layout(page, "cards")
            self.assertTrue(page.locator(".projection-card-list .projection-card").first.is_visible())

            self._open_columns_menu(page, force=True, button_text="Card Stats")
            self.assertTrue(page.locator(".multi-select-menu").first.is_visible())

            self._set_projection_layout(page, "table")
            first_row = page.locator(".projections-table tbody tr").first
            first_row.scroll_into_view_if_needed()
            self.assertTrue(first_row.is_visible())
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
