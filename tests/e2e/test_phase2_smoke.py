"""Phase-2 end-to-end smoke test (Playwright, headless).

Walks the full Phase-2 journey against a LIVE server (FastAPI serving the static
UI at /app/ + the real Gemini-backed agent): upload -> ask with live progress ->
memory follow-up -> cost meter -> history revisit + re-run. Override the base URL
with PHASE2_BASE_URL. Skips gracefully when the server is unreachable so the file
never hard-fails when the suite is collected without a running server.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("PHASE2_BASE_URL", "http://localhost:8001/app/")

# Generous — each answer makes a real Gemini call + runs generated pandas, and
# the journey exercises several such round-trips (ask, follow-up, re-run).
ANSWER_TIMEOUT_MS = 120_000


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
    # region + amount + a month column so a "break down by month" follow-up is
    # meaningful and memory (Q1 -> Q2) is genuinely exercised.
    p = tmp_path / "sales.csv"
    p.write_text(
        "region,amount,month\n"
        "North,100,2024-01\n"
        "South,200,2024-01\n"
        "North,150,2024-02\n"
        "West,300,2024-02\n"
        "South,50,2024-03\n"
        "West,250,2024-03\n"
        "North,120,2024-03\n"
    )
    return p


def _fail_if_answer_error(page: Page) -> None:
    if page.get_by_test_id("answer-error").count() > 0:
        pytest.fail("Agent run failed: " + page.get_by_test_id("answer-error").first.inner_text())


def test_phase2_smoke(page: Page, csv_path):
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

    # --- Remaining Phase-2 stub is present and labelled "Coming soon" ---
    expect(page.get_by_test_id("phase2-tag").first).to_be_visible()
    expect(page.get_by_test_id("phase2-tag").first).to_contain_text("Coming soon")

    # --- Upload a small CSV -> profile card appears (session is created) ---
    page.set_input_files('[data-testid="file-input"]', str(csv_path))

    profile = page.get_by_test_id("profile-card")
    expect(profile).to_be_visible(timeout=30_000)
    expect(page.get_by_test_id("dataset-stats")).to_contain_text("7")

    # --- Q1: ask a question; live progress shows, then a real answer ---
    page.get_by_test_id("question-input").fill("What is the total amount by region?")
    page.get_by_test_id("ask-button").click()

    # Live step progress becomes visible with at least one step during the run.
    progress = page.get_by_test_id("progress-steps")
    expect(progress).to_be_visible(timeout=15_000)
    assert page.get_by_test_id("progress-step").count() >= 1, "no live progress step rendered"

    answer1 = page.get_by_test_id("answer-block")
    expect(answer1.first).to_be_visible(timeout=ANSWER_TIMEOUT_MS)
    _fail_if_answer_error(page)
    assert page.get_by_test_id("answer-text").first.inner_text().strip(), "Q1 answer is empty"

    # Cost meter shows a non-empty tokens/$ value after the run.
    cost_meter = page.get_by_test_id("cost-meter")
    expect(cost_meter).to_be_visible()
    session_total = page.get_by_test_id("cost-session-total")
    expect(session_total).to_be_visible(timeout=15_000)
    expect(session_total).to_contain_text("tok")
    expect(session_total).to_contain_text("$")

    # --- Q2: a memory follow-up that needs Q1's context ---
    page.get_by_test_id("question-input").fill(
        "Now show only the region with the highest total."
    )
    page.get_by_test_id("ask-button").click()

    # A second answer block appears and is non-empty (memory path exercised).
    expect(page.get_by_test_id("answer-block")).to_have_count(2, timeout=ANSWER_TIMEOUT_MS)
    _fail_if_answer_error(page)
    answer_texts = page.get_by_test_id("answer-text")
    assert answer_texts.nth(1).inner_text().strip(), "Q2 (follow-up) answer is empty"

    # --- History lists >= 2 items; revisit one, then re-run it ---
    history = page.get_by_test_id("history-panel")
    expect(history).to_be_visible()
    items = page.get_by_test_id("history-item")
    expect(items).to_have_count(2, timeout=15_000)

    # Open the first saved run -> its answer renders in the detail overlay.
    items.first.click()
    detail = page.get_by_test_id("history-detail")
    expect(detail).to_be_visible()
    # 2 conversation answers + 1 in the detail overlay.
    expect(page.get_by_test_id("answer-block")).to_have_count(3, timeout=30_000)
    _fail_if_answer_error(page)

    # Re-run -> overlay closes and a NEW answer appends to the conversation.
    page.get_by_test_id("history-rerun").click()
    expect(detail).to_be_hidden(timeout=ANSWER_TIMEOUT_MS)
    # 3 conversation answers now (original 2 + the re-run), overlay gone.
    expect(page.get_by_test_id("answer-block")).to_have_count(3, timeout=ANSWER_TIMEOUT_MS)
    _fail_if_answer_error(page)

    # --- A remaining stub still shows "Coming soon" (stubs-vs-real visible) ---
    expect(page.get_by_test_id("phase2-tag").first).to_contain_text("Coming soon")
