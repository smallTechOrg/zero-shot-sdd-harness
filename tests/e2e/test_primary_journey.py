import pathlib
import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect

CSV_PATH = pathlib.Path("scripts/fixtures/sample_data.csv")


def test_user_gets_an_answer(page):
    """Full browser journey: upload CSV → ask a question → data analyst returns the correct answer."""
    page.goto("http://localhost:8001")

    # Upload the CSV via the hidden file input
    page.locator("#file-input").set_input_files(str(CSV_PATH))
    # Wait for the upload confirmation label to update
    expect(page.locator("#upload-label")).to_contain_text("sample_data.csv", timeout=5_000)

    page.get_by_role("textbox").fill("What is the total revenue across all months?")
    page.get_by_role("button", name="Analyse").click()

    # First .turn .a div should appear with the real answer (not the loading "…")
    answer_el = page.locator(".turn .a").first
    expect(answer_el).to_contain_text("767", timeout=90_000)
    expect(page.get_by_role("link", name="trace")).to_be_visible()
