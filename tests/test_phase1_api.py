"""API contract tests via TestClient (real Gemini for the /questions path)."""
import csv
import io

import pytest


def _csv_bytes(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode()


def test_post_datasets_returns_schema_and_counts(api_client):
    data = _csv_bytes([["region", "revenue"], ["West", 100], ["East", 200], ["West", 300]])
    r = api_client.post(
        "/datasets",
        files={"file": ("orders.csv", data, "text/csv")},
    )
    assert r.status_code == 200, r.text
    payload = r.json()["data"]
    assert payload["row_count"] == 3
    assert payload["column_count"] == 2
    names = {c["name"] for c in payload["schema"]}
    assert names == {"region", "revenue"}
    assert len(payload["sample_rows"]) <= 10
    assert payload["filename"] == "orders.csv"
    assert payload["id"]


def test_post_datasets_rejects_non_csv(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("data.json", b"{}", "application/json")},
    )
    assert r.status_code == 415
    assert r.json()["detail"]["code"] == "UNSUPPORTED_FORMAT"


def test_question_dataset_not_found(api_client):
    r = api_client.post("/questions", json={"dataset_id": "nope", "text": "x"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "DATASET_NOT_FOUND"


def test_get_question_not_found(api_client):
    r = api_client.get("/questions/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.usefixtures("_require_llm_key")
def test_full_contract_upload_ask_fetch(api_client):
    data = _csv_bytes([["region", "revenue"], ["West", 100], ["East", 200], ["West", 300]])
    up = api_client.post("/datasets", files={"file": ("orders.csv", data, "text/csv")})
    assert up.status_code == 200
    ds_id = up.json()["data"]["id"]

    ask = api_client.post(
        "/questions",
        json={"dataset_id": ds_id, "text": "What is the total revenue by region, highest first?"},
    )
    assert ask.status_code == 200, ask.text
    body = ask.json()["data"]

    # full payload shape
    assert body["status"] == "completed", body.get("error_message")
    assert body["answer"]
    assert isinstance(body["plan"], list) and len(body["plan"]) >= 1
    assert isinstance(body["steps"], list) and len(body["steps"]) >= 1
    step = body["steps"][0]
    for key in ("step_index", "language", "code", "result", "error", "latency_ms"):
        assert key in step
    assert body["cost"]["tokens_in"] > 0
    assert body["cost"]["tokens_out"] > 0
    assert body["cost"]["estimated_usd"] > 0
    assert "cost_guard_warning" in body

    # GET returns the same shape
    qid = body["id"]
    got = api_client.get(f"/questions/{qid}")
    assert got.status_code == 200
    gbody = got.json()["data"]
    assert gbody["id"] == qid
    assert gbody["answer"] == body["answer"]
    assert len(gbody["steps"]) == len(body["steps"])
