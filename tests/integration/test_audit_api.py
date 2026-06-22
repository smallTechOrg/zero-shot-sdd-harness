import io
import pytest

CSV_CONTENT = b"a,b\n1,2\n3,4\n"


def test_audit_empty(client):
    resp = client.get("/audit")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_audit_after_upload(client):
    resp = client.post("/sessions", json={})
    sid = resp.json()["data"]["session_id"]
    client.post(
        f"/sessions/{sid}/upload",
        files={"file": ("t.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
    )
    resp = client.get(f"/audit?session_id={sid}")
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["event_type"] == "file_upload"
