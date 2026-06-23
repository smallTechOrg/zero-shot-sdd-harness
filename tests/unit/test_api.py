"""API contract tests — no LLM key required."""
import io
import pytest
from fastapi.testclient import TestClient
from api import app


@pytest.fixture
def client(_isolated_db):
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


def test_upload_missing_session_header(client):
    """POST /datasets/upload without X-Session-ID returns 400."""
    csv_bytes = b"a,b\n1,2\n"
    r = client.post(
        "/datasets/upload",
        files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "MISSING_SESSION"


def test_upload_invalid_file_type(client):
    """POST /datasets/upload with non-CSV/Excel file returns 422."""
    r = client.post(
        "/datasets/upload",
        headers={"X-Session-ID": "test-session"},
        files={"file": ("bad.txt", io.BytesIO(b"not csv"), "text/plain")},
    )
    assert r.status_code == 422


def test_upload_and_list_datasets(client):
    """Upload CSV then list datasets."""
    session_id = "list-test-11111111-1111-1111-1111-111111111111"
    csv_bytes = b"product,sales\nWidget A,100\nWidget B,200\n"

    r = client.post(
        "/datasets/upload",
        headers={"X-Session-ID": session_id},
        files={"file": ("sales.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["row_count"] == 2
    assert "table_name" in data
    table_name = data["table_name"]

    # List should show it
    r2 = client.get("/datasets", headers={"X-Session-ID": session_id})
    assert r2.status_code == 200
    items = r2.json()["data"]
    assert any(d["table_name"] == table_name for d in items)


def test_list_datasets_missing_session(client):
    """GET /datasets without X-Session-ID returns 400."""
    r = client.get("/datasets")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "MISSING_SESSION"


def test_query_missing_session(client):
    """POST /query without X-Session-ID returns 400."""
    r = client.post("/query", json={"question": "hi", "dataset_table": "x_y"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "MISSING_SESSION"


def test_query_cross_session_forbidden(client):
    """POST /query with table from another session returns 403."""
    session_a = "session-a-11111111-1111-1111-1111-111111111111"
    session_b = "session-b-22222222-2222-2222-2222-222222222222"
    # Table belongs to session_a
    prefix_a = session_a.replace("-", "_")
    table = f"{prefix_a}_sales"

    r = client.post(
        "/query",
        headers={"X-Session-ID": session_b},
        json={"question": "How many?", "dataset_table": table},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "FORBIDDEN"


def test_audit_missing_session(client):
    """GET /audit without X-Session-ID returns 400."""
    r = client.get("/audit")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "MISSING_SESSION"


def test_audit_empty_for_new_session(client):
    """GET /audit for a session with no queries returns empty list."""
    session_id = "audit-test-11111111-1111-1111-1111-111111111111"
    r = client.get("/audit", headers={"X-Session-ID": session_id})
    assert r.status_code == 200
    assert r.json()["data"] == []
