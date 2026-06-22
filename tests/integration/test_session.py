"""Integration tests for session management and history endpoint."""
import pytest


def test_chat_creates_session_and_history_endpoint_works(app_client, uploaded_dataset):
    """POST /chat creates a session; GET /sessions/{id}/history returns turns."""
    r = app_client.post(
        "/chat",
        json={"message": "How many rows are in the dataset?"},
    )
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    hist_r = app_client.get(f"/sessions/{session_id}/history")
    assert hist_r.status_code == 200
    hist = hist_r.json()
    assert hist["session_id"] == session_id
    turns = hist["turns"]
    # Should have at least 2 turns: user + assistant
    assert len(turns) >= 2
    roles = [t["role"] for t in turns]
    assert "user" in roles
    assert "assistant" in roles


def test_session_turns_in_order(app_client, uploaded_dataset):
    """Turns in the history endpoint are returned in chronological order."""
    # First turn
    r1 = app_client.post("/chat", json={"message": "How many employees are in Marketing?"})
    assert r1.status_code == 200
    session_id = r1.json()["session_id"]

    # Second turn
    r2 = app_client.post(
        "/chat",
        json={"session_id": session_id, "message": "What is the average salary in HR?"},
    )
    assert r2.status_code == 200

    hist_r = app_client.get(f"/sessions/{session_id}/history")
    assert hist_r.status_code == 200
    turns = hist_r.json()["turns"]

    # At least 4 turns (2 user + 2 assistant)
    assert len(turns) >= 4

    # Verify turn_index ordering
    indices = [t["turn_index"] for t in turns]
    assert indices == sorted(indices), "Turns must be in ascending turn_index order"

    # First user message is the first question
    user_turns = [t for t in turns if t["role"] == "user"]
    assert "Marketing" in user_turns[0]["content"]


def test_nonexistent_session_history_returns_404(app_client):
    """GET /sessions/<nonexistent>/history must return 404."""
    r = app_client.get("/sessions/nonexistent-session-id-12345/history")
    assert r.status_code == 404
    body = r.json()
    assert "detail" in body


def test_session_persists_across_requests(app_client, uploaded_dataset):
    """Session ID from first request is valid in subsequent requests."""
    r1 = app_client.post("/chat", json={"message": "What columns does the employees table have?"})
    assert r1.status_code == 200
    session_id = r1.json()["session_id"]

    # Second request uses the session_id — history is included
    r2 = app_client.post(
        "/chat",
        json={"session_id": session_id, "message": "Show me the first 3 employees"},
    )
    assert r2.status_code == 200
    assert r2.json()["session_id"] == session_id

    # History should show all turns
    hist = app_client.get(f"/sessions/{session_id}/history").json()
    assert len(hist["turns"]) >= 4
