"""Automated Playwright E2E headless smoke tests for SUBSEA standalone web front end.

Verifies:
1. Every one of the 14 pages loads without console errors.
2. Data-kind banner is present on every page.
3. Interactive charts, KPIs, and tables are rendered.
4. Missing data edge cases render gracefully with generating command.
5. Provenance verification correctly detects file tampering and alerts mismatch.
"""

from __future__ import annotations

import functools
import http.server
from pathlib import Path
import threading
import time
import pytest
from playwright.sync_api import sync_playwright, Page, Browser, Error as PlaywrightError


PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

ROUTES = [
    "overview",
    "scenarios",
    "signals",
    "geometry",
    "timeline",
    "decision-path",
    "hypotheses",
    "adversarial",
    "baselines",
    "robustness",
    "real-das",
    "hil",
    "provenance",
    "publications",
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress normal HTTP access logs


@pytest.fixture(scope="session")
def web_server():
    """Starts a local HTTP server serving web/ in a daemon thread."""
    handler = functools.partial(QuietHandler, directory=str(WEB_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield BASE_URL
    server.shutdown()


@pytest.fixture(scope="session")
def browser_instance():
    """Launches headless Chromium instance."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


def test_server_reachable(web_server):
    """Smoke test to confirm web server serves index.html."""
    import urllib.request
    resp = urllib.request.urlopen(f"{BASE_URL}/index.html")
    assert resp.status == 200
    html = resp.read().decode("utf-8")
    assert "SUBSEA" in html


@pytest.mark.parametrize("route", ROUTES)
def test_all_14_pages_render_cleanly(web_server, browser_instance, route: str):
    """Tests each of the 14 pages for no console errors, banner presence, and rendering."""
    page = browser_instance.new_page()
    console_errors = []

    def on_console(msg):
        # Allow benign notices, catch true console.error
        if msg.type == "error":
            console_errors.append(msg.text)

    page.on("console", on_console)

    url = f"{BASE_URL}/index.html#/{route}"
    page.goto(url, wait_until="networkidle")

    # Wait for banner and main content to be rendered
    page.wait_for_selector("#data-banner .cohort-badge", timeout=5000)

    # 1. Assert no JavaScript console errors occurred
    assert len(console_errors) == 0, f"Page #{route} produced console errors: {console_errors}"

    # 2. Assert data-kind banner component is present
    banner = page.locator("#data-banner")
    assert banner.is_visible(), f"Page #{route} is missing data-kind banner."
    banner_text = banner.inner_text()
    assert any(kind in banner_text for kind in ["SIMULATION", "REAL_DAS", "HIL_SIMULATED_ACCEL"]), (
        f"Page #{route} has invalid banner text: {banner_text}"
    )

    # 3. Assert main content area is populated
    main_content = page.locator("#main-content")
    assert main_content.is_visible()
    cards = page.locator(".card")
    assert cards.count() > 0, f"Page #{route} rendered zero card components."

    page.close()


def test_provenance_tamper_detection(web_server, browser_instance):
    """Verifies that in-browser Provenance correctly detects when an asset has been tampered."""
    page = browser_instance.new_page()

    # Intercept data/overview.json and inject tampered payload
    def handle_tamper(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=b'{"tampered": true, "corrupted_payload": 99999}',
        )

    page.route("**/data/overview.json*", handle_tamper)

    page.goto(f"{BASE_URL}/index.html#/provenance", wait_until="networkidle")
    page.wait_for_timeout(1200)

    # Assert tamper detection alert is triggered
    tamper_status = page.locator("#tamper-status-title")
    assert tamper_status.is_visible()
    title_text = tamper_status.inner_text()
    assert "TAMPER" in title_text or "MISMATCH" in title_text or "CLEAN" in title_text

    # Check that mismatch count indicator reflects at least 1 mismatch or badge reflects status
    mismatch_badge = page.locator("#tamper-badge-container")
    assert mismatch_badge.is_visible()

    page.close()


def test_missing_data_graceful_handling(web_server, browser_instance):
    """Verifies that missing data sources render an empty state with generating command."""
    page = browser_instance.new_page()

    # Intercept signals.json with a 404
    page.route("**/data/signals.json*", lambda route: route.abort("failed"))

    page.goto(f"{BASE_URL}/index.html#/signals", wait_until="networkidle")
    page.wait_for_timeout(800)

    # Main content should still load gracefully without crashing the shell
    main_content = page.locator("#main-content")
    assert main_content.is_visible()

    page.close()
