import hashlib
import os
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

UPDATE_BASELINE_ENV_VAR = "FF_UPDATE_VISUAL_BASELINE"
UPDATE_BASELINE_ENABLED = {"1", "true", "yes", "on"}


class ProjectionsVisualRegressionE2ETests(unittest.TestCase):
    """Visual + sticky-column regression coverage for dense table layouts."""

    @classmethod
    def setUpClass(cls) -> None:
        if sync_playwright is None:
            raise unittest.SkipTest(
                "Playwright is not installed. Install test deps with: pip install -r requirements-dev.txt"
            )

        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.port = int(os.environ.get("FF_E2E_VISUAL_PORT", "8767"))
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

    def _wait_for_projection_request_idle(self, page, idle_seconds: float = 1.5, timeout_seconds: float = 45.0) -> None:
        tracker = {"last_request_ts": time.time()}

        def on_request(request) -> None:
            if "/api/projections/all" in request.url:
                tracker["last_request_ts"] = time.time()

        page.on("request", on_request)
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if time.time() - tracker["last_request_ts"] >= idle_seconds:
                return
            page.wait_for_timeout(200)
        raise TimeoutError("Projection requests did not settle before snapshot")

    def test_small_laptop_projections_table_visual_snapshot(self) -> None:
        context = self.browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        try:
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
            page.locator("#projections-year-filter").select_option(value="__career_totals__")
            page.wait_for_selector(".projections-table tbody tr", timeout=90000)
            page.wait_for_function(
                """
                () => {
                  const el = document.querySelector('.filter-bar .result-count');
                  if (!el) return false;
                  const m = (el.textContent || '').match(/[\\d,]+/);
                  if (!m) return false;
                  const n = parseInt(m[0].replaceAll(',', ''), 10);
                  return Number.isFinite(n) && n > 100;
                }
                """,
                timeout=90000,
            )
            self._wait_for_projection_request_idle(page)
            # Hide vertical scrollbar during capture so the baseline focuses on table structure/typography.
            page.add_style_tag(content=".table-scroll { overflow-y: hidden !important; }")

            table_wrapper = page.locator(".table-wrapper").first
            table_wrapper.scroll_into_view_if_needed()
            screenshot_bytes = table_wrapper.screenshot()

            baseline_path = self.repo_root / "tests" / "fixtures" / "visual" / "projections-table-small-laptop.png"
            should_update_baseline = (
                os.getenv(UPDATE_BASELINE_ENV_VAR, "").strip().lower() in UPDATE_BASELINE_ENABLED
            )

            if should_update_baseline:
                baseline_path.parent.mkdir(parents=True, exist_ok=True)
                baseline_path.write_bytes(screenshot_bytes)

            self.assertTrue(
                baseline_path.exists(),
                f"Missing baseline image at {baseline_path}. "
                f"Set {UPDATE_BASELINE_ENV_VAR}=1 to generate it.",
            )

            expected_hash = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
            actual_hash = hashlib.sha256(screenshot_bytes).hexdigest()
            self.assertEqual(
                actual_hash,
                expected_hash,
                f"Projections table visual regression detected. "
                f"Set {UPDATE_BASELINE_ENV_VAR}=1 to accept the new baseline.",
            )

            metrics = page.evaluate(
                """
                () => {
                  const wrapper = document.querySelector('.table-wrapper');
                  const projectionsTable = document.querySelector('.projections-table');
                  const scroller = projectionsTable ? projectionsTable.closest('.table-scroll') : null;
                  const row = projectionsTable ? projectionsTable.querySelector('tbody tr') : null;
                  const playerCell = row?.querySelector('td.player-name');
                  if (!wrapper || !scroller || !row || !playerCell) {
                    return { ready: false };
                  }

                  scroller.scrollLeft = scroller.scrollWidth;
                  const wrapperRect = wrapper.getBoundingClientRect();
                  const playerRect = playerCell.getBoundingClientRect();

                  const visibleNext = Array.from(row.querySelectorAll('td'))
                    .filter((el) => !el.classList.contains('index-col') && !el.classList.contains('player-name'))
                    .map((el) => ({ el, rect: el.getBoundingClientRect() }))
                    .find(({ rect }) => rect.left > playerRect.right - 1 && rect.left < window.innerWidth);

                  const longestName = Array.from(document.querySelectorAll('.projections-table td.player-name'))
                    .map((el) => (el.textContent || '').trim())
                    .sort((a, b) => b.length - a.length)[0] || '';

                  const largeNumberSample = Array.from(document.querySelectorAll('.projections-table td.num'))
                    .map((el) => (el.textContent || '').trim())
                    .find((txt) => /\\d{4,}|,/.test(txt)) || '';

                  return {
                    ready: true,
                    player_left_delta: Math.abs(playerRect.left - wrapperRect.left),
                    player_next_overlap_px: visibleNext ? Math.max(0, playerRect.right - visibleNext.rect.left) : null,
                    player_scroll_overflow: playerCell.scrollWidth - playerCell.clientWidth,
                    longest_name_len: longestName.length,
                    large_number_sample: largeNumberSample,
                  };
                }
                """
            )

            self.assertTrue(metrics.get("ready"), "Expected projections table row for sticky checks")
            self.assertLessEqual(metrics["player_left_delta"], 2.0)
            self.assertIsNotNone(metrics["player_next_overlap_px"])
            self.assertLessEqual(metrics["player_next_overlap_px"], 1.0)
            self.assertLessEqual(metrics["player_scroll_overflow"], 0)
            self.assertGreaterEqual(metrics["longest_name_len"], 10)
            self.assertTrue(metrics["large_number_sample"])
        finally:
            context.close()

    def test_small_laptop_rankings_pinned_columns_no_overlap(self) -> None:
        context = self.browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        try:
            page.goto(self.base_url, wait_until="domcontentloaded", timeout=90000)
            page.locator(".embedded-calculator-toggle").first.click()
            page.wait_for_selector(".calc-sidebar", timeout=20000)

            setup_group = page.locator(".calc-sidebar .form-group").filter(
                has=page.locator("label", has_text="Setup")
            ).first
            setup_group.locator("select").first.select_option("points")

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
            page.wait_for_selector(".rankings-table tbody tr.clickable-row", timeout=30000)

            metrics = page.evaluate(
                """
                () => {
                  const rankingsTable = document.querySelector('.rankings-table');
                  const scroller = rankingsTable ? rankingsTable.closest('.table-scroll') : null;
                  const row = rankingsTable ? rankingsTable.querySelector('tbody tr.clickable-row') : null;
                  if (!scroller || !row) return { ready: false };

                  scroller.scrollLeft = scroller.scrollWidth;

                  const rankCell = row.querySelector('td.rank-pin-rank');
                  const playerCell = row.querySelector('td.rank-pin-player');
                  const valueCell = row.querySelector('td.rank-pin-value');
                  if (!rankCell || !playerCell || !valueCell) return { ready: false };

                  const rankRect = rankCell.getBoundingClientRect();
                  const playerRect = playerCell.getBoundingClientRect();
                  const valueRect = valueCell.getBoundingClientRect();

                  const visibleNext = Array.from(row.querySelectorAll('td'))
                    .filter((el) =>
                      !el.classList.contains('rank-pin-rank') &&
                      !el.classList.contains('rank-pin-player') &&
                      !el.classList.contains('rank-pin-value')
                    )
                    .map((el) => ({ el, rect: el.getBoundingClientRect() }))
                    .find(({ rect }) => rect.left > valueRect.right - 1 && rect.left < window.innerWidth);

                  const playerName = (playerCell.textContent || '').trim();
                  const largeNumberSample = Array.from(document.querySelectorAll('.rankings-table td.num'))
                    .map((el) => (el.textContent || '').trim())
                    .find((txt) => /\\d{4,}|,/.test(txt)) || '';

                  return {
                    ready: true,
                    rank_player_overlap_px: Math.max(0, rankRect.right - playerRect.left),
                    player_value_overlap_px: Math.max(0, playerRect.right - valueRect.left),
                    value_next_overlap_px: visibleNext ? Math.max(0, valueRect.right - visibleNext.rect.left) : null,
                    player_scroll_overflow: playerCell.scrollWidth - playerCell.clientWidth,
                    player_name_len: playerName.length,
                    large_number_sample: largeNumberSample,
                  };
                }
                """
            )

            self.assertTrue(metrics.get("ready"), "Expected rankings row for sticky checks")
            self.assertLessEqual(metrics["rank_player_overlap_px"], 1.0)
            self.assertLessEqual(metrics["player_value_overlap_px"], 1.0)
            self.assertIsNotNone(metrics["value_next_overlap_px"])
            self.assertLessEqual(metrics["value_next_overlap_px"], 1.0)
            self.assertLessEqual(metrics["player_scroll_overflow"], 0)
            self.assertGreaterEqual(metrics["player_name_len"], 10)
            self.assertTrue(metrics["large_number_sample"])
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main()
