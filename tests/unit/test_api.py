"""API contract tests — no LLM key required, the graph is not invoked."""
import io
import json
from unittest.mock import patch

from sqlalchemy.orm import Session

from db.models import DatasetRow, RunRow


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_upload_rejects_non_csv(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_REQUEST"


def test_upload_rejects_empty_file(api_client):
    r = api_client.post(
        "/datasets",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 400


def test_upload_csv_returns_schema_and_sample(api_client):
    csv = b"city,pop\nA,10\nB,20\n"
    r = api_client.post(
        "/datasets",
        files={"file": ("cities.csv", io.BytesIO(csv), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["row_count"] == 2
    names = [c["name"] for c in data["schema"]]
    assert "city" in names and "pop" in names
    assert len(data["sample"]) == 2


def test_create_run_unknown_dataset_404(api_client):
    r = api_client.post("/datasets/nope/runs", json={"question": "x?"})
    assert r.status_code == 404


def test_create_run_empty_question_400(api_client, _isolated_db):
    with Session(_isolated_db) as s:
        ds = DatasetRow(filename="x.csv", path="/tmp/x.csv", row_count=1,
                        schema_json="[]", sample_json="[]")
        s.add(ds)
        s.commit()
        ds_id = ds.id

    r = api_client.post(f"/datasets/{ds_id}/runs", json={"question": "   "})
    assert r.status_code == 400


def test_create_run_dispatches_and_returns_running(api_client, _isolated_db):
    with Session(_isolated_db) as s:
        ds = DatasetRow(filename="x.csv", path="/tmp/x.csv", row_count=1,
                        schema_json="[]", sample_json="[]")
        s.add(ds)
        s.commit()
        ds_id = ds.id

    # Patch the dispatcher so no real agent runs — we only test the contract.
    with patch("api.analysis._dispatch_run") as disp:
        r = api_client.post(f"/datasets/{ds_id}/runs", json={"question": "How many?"})
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["status"] == "running"
    assert body["run_id"]
    disp.assert_called_once()


def test_get_run_not_found_404(api_client):
    r = api_client.get("/runs/nonexistent/")
    # trailing slash not part of route; check the canonical path
    r = api_client.get("/runs/nonexistent")
    assert r.status_code == 404


def test_get_run_returns_audit_trail(api_client, _isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(
            dataset_id="ds1",
            question="How many?",
            plan="group by status",
            status="completed",
            answer="42",
            steps_json=json.dumps([{"attempt": 1, "code": "result = 42",
                                    "ok": True, "error": None}]),
            table_json=json.dumps([{"status": "x", "count": 42}]),
            tokens=123,
        )
        s.add(run)
        s.commit()
        run_id = run.id

    r = api_client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["answer"] == "42"
    assert data["plan"] == "group by status"
    assert data["steps"][0]["code"] == "result = 42"
    assert data["table"][0]["count"] == 42
    assert data["tokens"] == 123
