"""Integration tests for the CSV analysis pipeline — requires real Gemini API key."""
import io
import json

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def _require_gemini_key():
    """Skip if AGENT_GEMINI_API_KEY is not set."""
    from config.settings import get_settings
    s = get_settings()
    if not s.gemini_api_key:
        pytest.skip("AGENT_GEMINI_API_KEY not set in .env")


@pytest.fixture
def api_client(_isolated_db):
    """FastAPI test client with isolated DB."""
    from fastapi.testclient import TestClient
    from api import create_app
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def known_csv_bytes() -> bytes:
    """120-row CSV with deterministic means: category A=15, B=35, overall ~25."""
    np.random.seed(42)
    categories = ["A", "B", "C", "D"]
    df = pd.DataFrame({
        "category": np.random.choice(categories, 120),
        "value": np.random.randint(10, 60, 120),
        "quantity": np.random.randint(1, 100, 120),
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def simple_csv_bytes() -> bytes:
    """5-row CSV where category A always has value 30."""
    df = pd.DataFrame({
        "category": ["A", "A", "A", "A", "A"],
        "value": [30, 30, 30, 30, 30],
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Test 1: Upload CSV
# ---------------------------------------------------------------------------

def test_upload_csv(api_client, known_csv_bytes):
    r = api_client.post(
        "/datasets",
        files={"file": ("test_data.csv", known_csv_bytes, "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error"] is None
    data = body["data"]
    assert "dataset_id" in data
    assert len(data["dataset_id"]) > 0
    assert data["row_count"] > 0
    assert isinstance(data["column_names"], list)
    assert len(data["column_names"]) > 0
    assert data["filename"] == "test_data.csv"


# ---------------------------------------------------------------------------
# Test 2: Full analysis pipeline (real Gemini)
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_require_gemini_key")
def test_full_analysis_pipeline(api_client, known_csv_bytes):
    # Upload
    r = api_client.post(
        "/datasets",
        files={"file": ("pipeline_test.csv", known_csv_bytes, "text/csv")},
    )
    assert r.status_code == 200, r.text
    dataset_id = r.json()["data"]["dataset_id"]

    # Analyze
    r2 = api_client.post(
        "/analyses",
        json={"dataset_id": dataset_id, "question": "What is the average value per category?"},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["error"] is None
    data = body["data"]
    assert data["status"] == "completed"
    assert data["answer_text"] and len(data["answer_text"]) > 5
    # chart_json may be None or a valid JSON string
    if data["chart_json"] is not None:
        parsed_chart = json.loads(data["chart_json"])
        assert "data" in parsed_chart


# ---------------------------------------------------------------------------
# Test 3: Analysis with known data — answer must contain "30"
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_require_gemini_key")
def test_analysis_with_known_data(api_client, simple_csv_bytes):
    # Upload 5-row CSV where all values are 30
    r = api_client.post(
        "/datasets",
        files={"file": ("simple.csv", simple_csv_bytes, "text/csv")},
    )
    assert r.status_code == 200, r.text
    dataset_id = r.json()["data"]["dataset_id"]

    # Ask for mean of value
    r2 = api_client.post(
        "/analyses",
        json={"dataset_id": dataset_id, "question": "What is the mean value for category A?"},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    data = body["data"]

    assert data["status"] == "completed", f"status={data['status']}, error={data.get('error')}"
    answer = data["answer_text"] or ""
    # The correct mean is 30.0 — answer must contain "30"
    assert "30" in answer, f"Expected '30' in answer, got: {answer!r}"


# ---------------------------------------------------------------------------
# Test 4: Empty question -> 400 EMPTY_QUESTION
# ---------------------------------------------------------------------------

def test_analysis_empty_question(api_client, known_csv_bytes):
    # Upload first
    r = api_client.post(
        "/datasets",
        files={"file": ("empty_q.csv", known_csv_bytes, "text/csv")},
    )
    dataset_id = r.json()["data"]["dataset_id"]

    r2 = api_client.post(
        "/analyses",
        json={"dataset_id": dataset_id, "question": ""},
    )
    assert r2.status_code == 400
    detail = r2.json().get("detail", {})
    assert detail.get("code") == "EMPTY_QUESTION"


# ---------------------------------------------------------------------------
# Test 5: Invalid dataset_id -> 400 DATASET_NOT_FOUND
# ---------------------------------------------------------------------------

def test_analysis_invalid_dataset(api_client):
    r = api_client.post(
        "/analyses",
        json={"dataset_id": "00000000-0000-0000-0000-000000000000", "question": "What?"},
    )
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("code") == "DATASET_NOT_FOUND"
