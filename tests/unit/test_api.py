"""API contract tests — no LLM key required."""
import io


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_upload_non_csv_returns_400(api_client):
    r = api_client.post(
        "/sessions",
        files={"file": ("data.txt", io.BytesIO(b"a,b\n1,2"), "text/plain")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_CSV"


def test_question_session_not_found(api_client):
    r = api_client.post(
        "/sessions/nonexistent/questions",
        json={"question": "What?"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "SESSION_NOT_FOUND"


def test_question_empty_rejected(api_client):
    # Upload first so session exists in memory
    csv_bytes = b"name,age\nAlice,30\n"
    r_upload = api_client.post(
        "/sessions",
        files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    session_id = r_upload.json()["data"]["session_id"]

    r = api_client.post(
        f"/sessions/{session_id}/questions",
        json={"question": ""},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "EMPTY_QUESTION"


def test_upload_empty_csv_returns_400(api_client):
    r = api_client.post(
        "/sessions",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 400


def test_upload_success_response_shape(api_client):
    csv_bytes = b"col1,col2\nval1,val2\n"
    r = api_client.post(
        "/sessions",
        files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    data = body["data"]
    assert "session_id" in data
    assert "columns" in data
    assert "row_count" in data
