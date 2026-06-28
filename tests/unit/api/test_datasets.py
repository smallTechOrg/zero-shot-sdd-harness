"""Datasets API contract tests (spec/api.md).

Upload / fetch / error cases need no LLM. One real end-to-end ``ask`` hits real
Gemini (gated on the key being present).
"""
from pathlib import Path

import pytest

_FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
_SALES = _FIXTURES / "sales.csv"


def _upload(api_client, path: Path):
    with path.open("rb") as fh:
        return api_client.post(
            "/datasets",
            files={"file": (path.name, fh, "text/csv")},
        )


def test_post_datasets_returns_profile(api_client):
    r = _upload(api_client, _SALES)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"]
    assert data["name"] == "sales.csv"
    assert data["status"] == "ready"
    assert data["row_count"] > 0
    # columns + profile present and aggregate-only (no raw rows)
    names = {c["name"] for c in data["columns"]}
    assert {"region", "month", "sales"} <= names
    assert data["profile"]["row_count"] == data["row_count"]
    assert any(c["name"] == "sales" for c in data["profile"]["columns"])


def test_get_dataset_returns_profile(api_client):
    created = _upload(api_client, _SALES).json()["data"]
    r = api_client.get(f"/datasets/{created['id']}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == created["id"]
    assert data["name"] == "sales.csv"
    assert data["status"] == "ready"


def test_get_dataset_not_found(api_client):
    r = api_client.get("/datasets/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_post_datasets_rejects_non_csv(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_FILE"


def test_post_datasets_rejects_empty(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_FILE"


def test_ask_empty_question_rejected(api_client):
    created = _upload(api_client, _SALES).json()["data"]
    r = api_client.post(f"/datasets/{created['id']}/ask", json={"question": "   "})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "EMPTY_QUESTION"


def test_ask_dataset_not_found(api_client):
    r = api_client.post("/datasets/does-not-exist/ask", json={"question": "How many rows?"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.usefixtures("_require_llm_key")
def test_ask_returns_answer_shape_real(api_client):
    """One real end-to-end ask via the HTTP surface against real Gemini."""
    created = _upload(api_client, _SALES).json()["data"]
    r = api_client.post(
        f"/datasets/{created['id']}/ask",
        json={"question": "Which region had the highest total sales?"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["run_id"]
    assert data["status"] == "completed", data.get("error_message")
    assert data["answer"]
    assert data["sql"]
    assert isinstance(data["trace"], list) and data["trace"]
    assert data["cost_usd"] >= 0
    # The answer should name the dominant region.
    assert "west" in data["answer"].lower() or "West" in str(data.get("table"))
