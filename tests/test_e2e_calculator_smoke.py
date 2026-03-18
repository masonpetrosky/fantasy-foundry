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
        self._wait_for_overlay_visible(page)

    def _wait_for_overlay_visible(self, page) -> None:
        page.wait_for_selector(".projections-overlay-message", state="visible", timeout=60000)

    def _assert_apply_status(self, page) -> int:
        status_text = page.locator(".calc-status").first.inner_text().strip()
        match = re.search(r"Applied\s+([\d,]+)\s+players\s+to\s+the\s+table\.", status_text)
        self.assertIsNotNone(match, f"Expected apply-success status, got {status_text!r}")
        total_count = int(match.group(1).replace(",", ""))
        self.assertGreater(total_count, 0, "Expected at least one applied player")
        return total_count

    def _assert_overlay_banner(self, page, expected_count: int) -> None:
        overlay = page.locator(".projections-overlay-message").first
        overlay_text = overlay.inner_text().strip()
        self.assertIn("calculator-adjusted dynasty values", overlay_text.lower())
        self.assertIn("Points mode", overlay_text)
        self.assertIn("Start 2026", overlay_text)
        self.assertIn("20-year horizon", overlay_text)
        match = re.search(r"\(([\d,]+)\s+available\)", overlay_text)
        self.assertIsNotNone(match, f"Expected overlay availability count, got {overlay_text!r}")
        available_count = int(match.group(1).replace(",", ""))
        self.assertEqual(available_count, expected_count)

    def _assert_overlay_explanation_toggle(self, page) -> None:
        overlay = page.locator(".projections-overlay-message").first
        why_button = overlay.get_by_role("button", name="Why this changed")
        why_button.scroll_into_view_if_needed()
        why_button.click()
        why_copy = page.locator(".overlay-why-copy").first
        why_copy.wait_for(state="visible", timeout=10000)
        self.assertIn("league setup", why_copy.inner_text().lower())
        overlay.get_by_role("button", name="Hide why this changed").click()
        why_copy.wait_for(state="hidden", timeout=10000)

    def _clear_overlay_and_assert_reset(self, page) -> None:
        overlay = page.locator(".projections-overlay-message").first
        clear_button = overlay.get_by_role("button", name="Clear applied values")
        clear_button.scroll_into_view_if_needed()
        clear_button.click(force=True)
        page.wait_for_selector(".projections-overlay-message", state="hidden", timeout=10000)

    def _close_mobile_sheet(self, page) -> None:
        close_button = page.get_by_role("button", name="Close calculator")
        close_button.click()
        page.wait_for_selector(".mobile-sheet", state="hidden", timeout=10000)

    def test_desktop_calculator_polish_smoke(self) -> None:
        context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        try:
            self._open_calculator(page)
            self._assert_preset_save_and_select_load_flow(page)
            self._switch_to_points_mode(page)
            self._run_calculation_and_wait(page)
            applied_count = self._assert_apply_status(page)
            self._assert_overlay_banner(page, applied_count)
            self._assert_overlay_explanation_toggle(page)
            self._clear_overlay_and_assert_reset(page)
        finally:
            context.close()

    def test_mobile_calculator_polish_smoke(self) -> None:
        context = self.browser.new_context(**self.playwright.devices["iPhone 13"])
        page = context.new_page()
        try:
            self._open_calculator(page)
            self._switch_to_points_mode(page)
            self._run_calculation_and_wait(page)
            applied_count = self._assert_apply_status(page)
            self._assert_overlay_banner(page, applied_count)

            overlay = page.locator(".projections-overlay-message").first
            overlay.scroll_into_view_if_needed()
            self.assertTrue(overlay.is_visible())

            viewport_width = int(page.evaluate("window.innerWidth"))
            overlay_width = float(
                page.evaluate(
                    "() => document.querySelector('.projections-overlay-message').getBoundingClientRect().width"
                )
            )
            self.assertLessEqual(round(overlay_width), viewport_width)

            self._close_mobile_sheet(page)
            self._assert_overlay_explanation_toggle(page)
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
