"""Integration tests for POST /chat — real Gemini API calls."""
import pytest


def test_chat_returns_200_with_response(app_client, uploaded_dataset):
    """Chat with an uploaded dataset — Gemini must respond with non-empty markdown."""
    r = app_client.post(
        "/chat",
        json={"message": "How many employees are there?"},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "session_id" in body
    assert isinstance(body["session_id"], str)
    assert len(body["session_id"]) > 0
    assert "response_markdown" in body
    assert isinstance(body["response_markdown"], str)
    assert len(body["response_markdown"]) > 0
    assert "latency_ms" in body
    assert body["latency_ms"] > 0


def test_chat_creates_audit_log(app_client, uploaded_dataset):
    """After a chat turn, the audit log must have an entry for the session."""
    import data_analyst.db.session as session_mod
    from data_analyst.db.models import AuditLog

    r = app_client.post(
        "/chat",
        json={"message": "What departments exist in the data?"},
    )
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    # Check audit log via direct DB access
    factory = session_mod._SessionLocal
    with factory() as db:
        logs = db.query(AuditLog).filter(AuditLog.session_id == session_id).all()
        assert len(logs) >= 1
        assert logs[0].user_question == "What departments exist in the data?"
        assert logs[0].latency_ms is not None and logs[0].latency_ms > 0


def test_chat_maintains_session_across_turns(app_client, uploaded_dataset):
    """Second message with same session_id continues the conversation."""
    r1 = app_client.post(
        "/chat",
        json={"message": "How many employees are in Engineering?"},
    )
    assert r1.status_code == 200
    session_id = r1.json()["session_id"]

    r2 = app_client.post(
        "/chat",
        json={"session_id": session_id, "message": "What is their average salary?"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    # Same session preserved
    assert body2["session_id"] == session_id
    assert len(body2["response_markdown"]) > 0


def test_chat_refuses_destructive_sql(app_client, uploaded_dataset):
    """Asking to drop a table must result in a refusal, not an error."""
    r = app_client.post(
        "/chat",
        json={"message": "Please drop the employees table"},
    )
    assert r.status_code == 200
    body = r.json()
    # Response should contain a refusal, not an empty string
    response_lower = body["response_markdown"].lower()
    # Agent should refuse or explain it cannot do destructive operations
    assert any(word in response_lower for word in [
        "cannot", "can't", "unable", "not allowed", "destructive", "not permitted",
        "drop", "refuse", "don't", "don't", "won't", "not able"
    ])


def test_chat_empty_message_returns_422(app_client):
    """Empty message must return 422."""
    r = app_client.post("/chat", json={"message": ""})
    assert r.status_code == 422

    r2 = app_client.post("/chat", json={"message": "   "})
    assert r2.status_code == 422


def test_chat_nonexistent_session_creates_new(app_client):
    """Sending a non-existent session_id creates a new session (or the server handles gracefully)."""
    # With no data uploaded, Gemini should respond saying no tables available
    r = app_client.post(
        "/chat",
        json={"session_id": "00000000-0000-0000-0000-000000000000", "message": "What tables do I have?"},
    )
    # Should not 500 — either 200 (new session) or 404
    assert r.status_code in (200, 404)


def test_chat_with_no_datasets_graceful_response(app_client):
    """Without any uploaded datasets, agent should respond gracefully."""
    r = app_client.post(
        "/chat",
        json={"message": "What data do I have?"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["response_markdown"]) > 0
    # No SQL executed, no datasets touched
    assert body["generated_sql"] is None or body["datasets_touched"] == []


def test_chat_response_has_correct_fields(app_client, uploaded_dataset):
    """Verify all expected fields in the response body."""
    r = app_client.post(
        "/chat",
        json={"message": "Show me the top 5 highest paid employees"},
    )
    assert r.status_code == 200
    body = r.json()
    required_fields = {"session_id", "response_markdown", "generated_sql", "datasets_touched", "row_count_returned", "latency_ms"}
    assert required_fields.issubset(body.keys())
    assert isinstance(body["datasets_touched"], list)
