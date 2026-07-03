"""Phase-1 end-to-end smoke test (Playwright, headless).

Runs against a LIVE server (FastAPI serving the static UI at /app/ + the real
Gemini-backed agent). Override the base URL with PHASE1_BASE_URL. Skips
gracefully when the server is unreachable so the file never hard-fails when the
suite is collected without a running server.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("PHASE1_BASE_URL", "http://localhost:8001/app/")

# Generous — the answer path makes a real Gemini call + runs generated pandas.
ANSWER_TIMEOUT_MS = 90_000


def _server_reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status < 500
    except (urllib.error.URLError, OSError, ValueError):
        return False


@pytest.fixture(autouse=True)
def _require_server():
    if not _server_reachable(BASE_URL):
        pytest.skip(f"Server not reachable at {BASE_URL} — start it to run the e2e smoke.")


@pytest.fixture
def csv_path(tmp_path):
    p = tmp_path / "sales.csv"
    p.write_text(
        "region,amount\n"
        "North,100\n"
        "South,200\n"
        "North,150\n"
        "West,300\n"
        "South,50\n"
        "West,250\n"
    )
    return p


def test_phase1_smoke(page: Page, csv_path):
    page.set_default_timeout(15_000)
    page.goto(BASE_URL)

    # --- Empty state renders AND is styled (Tailwind utilities loaded) ---
    upload = page.get_by_test_id("upload-box")
    expect(upload).to_be_visible()
    expect(page.get_by_test_id("empty-state")).to_be_visible()

    border_style = upload.evaluate("el => getComputedStyle(el).borderStyle")
    assert "dashed" in border_style, (
        f"upload box border-style is '{border_style}' — Tailwind utilities did not load "
        "(page is unstyled)."
    )

    # --- Labelled Phase-2 stubs are present and marked "Coming soon" ---
    expect(page.get_by_test_id("phase2-tag").first).to_be_visible()
    assert page.get_by_test_id("phase2-tag").first.inner_text().strip() != ""
    expect(page.get_by_test_id("phase2-tag").first).to_contain_text("Coming soon")

    # --- Upload a small CSV -> profile card appears ---
    page.set_input_files('[data-testid="file-input"]', str(csv_path))

    profile = page.get_by_test_id("profile-card")
    expect(profile).to_be_visible(timeout=30_000)
    # Exact row count (6 data rows) shown in the stats line.
    expect(page.get_by_test_id("dataset-stats")).to_contain_text("6")

    # --- Ask a question -> real answer block (real Gemini call) ---
    page.get_by_test_id("question-input").fill("What is the total amount by region?")
    page.get_by_test_id("ask-button").click()

    answer = page.get_by_test_id("answer-block")
    expect(answer).to_be_visible(timeout=ANSWER_TIMEOUT_MS)

    # If the run failed, surface its error rather than asserting success fields.
    if page.get_by_test_id("answer-error").count() > 0:
        pytest.fail(
            "Agent run failed: " + page.get_by_test_id("answer-error").inner_text()
        )

    # Plain-language answer is non-empty.
    answer_text = page.get_by_test_id("answer-text").inner_text().strip()
    assert answer_text, "answer_text is empty"

    # A chart rendered (vega-embed produces an <svg> inside chart-view).
    chart = page.get_by_test_id("chart-view")
    expect(chart).to_be_visible(timeout=15_000)
    expect(chart.locator("svg, canvas")).to_have_count(1, timeout=15_000)

    # Summary table present.
    expect(page.get_by_test_id("summary-table")).to_be_visible()

    # "Show code" reveals non-empty code.
    code_panel = page.get_by_test_id("code-panel")
    expect(code_panel).to_be_visible()
    code_panel.locator("summary").click()
    code_text = page.get_by_test_id("code-block").inner_text().strip()
    assert code_text, "'Show code' revealed an empty code block"
