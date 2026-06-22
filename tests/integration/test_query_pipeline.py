"""End-to-end query pipeline against REAL Gemini. Requires AGENT_GEMINI_API_KEY."""
import io

import pytest
from sqlalchemy.orm import Session as DBSession

import db.session as session_module
from db.models import AuditLog

CSV = b"region,revenue\nNorth,100\nSouth,250\nNorth,50\nWest,300\n"


def _upload(api_client, content=CSV, name="orders.csv"):
    return api_client.post(
        "/datasets",
        files={"file": (name, io.BytesIO(content), "text/csv")},
    )


def test_upload_registers_dataset(api_client):
    r = _upload(api_client)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 4
    names = [c["name"] for c in data["schema"]]
    assert names == ["region", "revenue"]

    # listed
    lst = api_client.get("/datasets").json()["data"]["datasets"]
    assert any(d["id"] == data["id"] for d in lst)


def test_upload_empty_file_is_bad_request(api_client):
    r = _upload(api_client, content=b"")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_REQUEST"


def test_query_unknown_session_not_found(api_client):
    ds = _upload(api_client).json()["data"]
    r = api_client.post(
        "/sessions/does-not-exist/query",
        json={"dataset_id": ds["id"], "question": "x"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.usefixtures("_require_llm_key")
def test_full_query_pipeline_real_gemini(api_client):
    ds = _upload(api_client).json()["data"]
    session_id = api_client.post("/sessions").json()["data"]["id"]

    r = api_client.post(
        f"/sessions/{session_id}/query",
        json={"dataset_id": ds["id"], "question": "What is the total revenue by region?"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    assert body["answer"] and isinstance(body["answer"], str)
    assert body["sql"] and "select" in body["sql"].lower()
    assert "columns" in body["result"] and "rows" in body["result"]
    assert len(body["result"]["rows"]) >= 1
    assert body["message_id"]

    # audit log written with status success
    with DBSession(session_module._engine) as s:
        audits = s.query(AuditLog).filter(AuditLog.operation == "query").all()
    assert any(a.status == "success" and a.row_count is not None for a in audits)

    # persistence: messages survive a fresh read (user + assistant)
    msgs = api_client.get(f"/sessions/{session_id}/messages").json()["data"]["messages"]
    roles = [m["role"] for m in msgs]
    assert "user" in roles and "assistant" in roles
    assistant = next(m for m in msgs if m["role"] == "assistant")
    assert assistant["result"] is not None
    assert assistant["sql"]
