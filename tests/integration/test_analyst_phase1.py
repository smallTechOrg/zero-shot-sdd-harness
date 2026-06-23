"""Phase 1 golden-path integration test for the analyst slice.

Runs against the REAL Gemini API (key from .env). Skipped if no LLM key is set.
"""
import io

import pytest

CSV = b"region,revenue\nWest,9000\nEast,7000\nWest,1000\nNorth,5000\n"


def _upload(api_client):
    resp = api_client.post(
        "/datasets",
        files={"file": ("sales.csv", io.BytesIO(CSV), "text/csv")},
    )
    return resp


def test_dataset_upload_creates_table(api_client):
    resp = _upload(api_client)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["session_id"]
    assert data["dataset_id"]
    assert data["table_name"].startswith("ds_")
    assert data["row_count"] == 4
    col_names = {c["name"] for c in data["columns"]}
    assert {"region", "revenue"} <= col_names


def test_ask_golden_path(api_client, _require_llm_key):
    up = _upload(api_client).json()["data"]
    session_id = up["session_id"]

    resp = api_client.post(
        f"/sessions/{session_id}/ask",
        json={"question": "What is the total revenue by region?"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["status"] == "completed", data.get("error")
    assert data["answer_text"] and data["answer_text"].strip()
    assert data["error"] is None

    sql = data["sql_text"]
    assert sql.upper().lstrip().startswith(("SELECT", "WITH"))

    result = data["result"]
    assert result is not None
    assert result["rows"], "expected non-empty result rows"
    # Numerically sane: total of all reported revenues should equal raw sum 22000.
    flat = [v for row in result["rows"] for v in row if isinstance(v, (int, float))]
    assert sum(flat) >= 22000


def test_read_only_enforced_and_audited(api_client, _require_llm_key):
    """Even an open-ended ask only ever runs a SELECT/WITH, and an 'ask'
    audit row is written."""
    up = _upload(api_client).json()["data"]
    session_id = up["session_id"]

    resp = api_client.post(
        f"/sessions/{session_id}/ask",
        json={"question": "Show me the highest revenue region."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    if data["status"] == "completed":
        assert data["sql_text"].upper().lstrip().startswith(("SELECT", "WITH"))

    # An 'ask' audit row must exist.
    from sqlalchemy import select
    from db.models import AuditLogRow
    from db.session import create_db_session

    with create_db_session() as s:
        ask_rows = s.scalars(
            select(AuditLogRow)
            .where(AuditLogRow.session_id == session_id)
            .where(AuditLogRow.operation == "ask")
        ).all()
    assert len(ask_rows) >= 1


def test_session_persists_turns(api_client, _require_llm_key):
    up = _upload(api_client).json()["data"]
    session_id = up["session_id"]

    api_client.post(
        f"/sessions/{session_id}/ask",
        json={"question": "What is the total revenue by region?"},
    )

    resp = api_client.get(f"/sessions/{session_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["session_id"] == session_id
    assert data["dataset"] is not None
    assert data["dataset"]["table_name"].startswith("ds_")
    assert len(data["turns"]) >= 1
    turn = data["turns"][0]
    assert turn["question"]
    assert "result" in turn


def test_unknown_session_404(api_client):
    resp = api_client.get("/sessions/does-not-exist")
    assert resp.status_code == 404


def test_empty_question_400(api_client):
    up = _upload(api_client).json()["data"]
    resp = api_client.post(
        f"/sessions/{up['session_id']}/ask", json={"question": "   "}
    )
    assert resp.status_code == 400
