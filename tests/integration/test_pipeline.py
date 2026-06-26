"""Integration tests for the pandas Q&A pipeline — requires real AGENT_GEMINI_API_KEY."""
import io
import pytest


@pytest.mark.usefixtures("_require_gemini_key")
def test_graph_runner_end_to_end(api_client):
    """Full HTTP round-trip: upload CSV + ask question."""
    csv_content = "name,score\nAlice,95\nBob,87\nCarol,92\n"
    r_upload = api_client.post(
        "/sessions",
        files={"file": ("grades.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert r_upload.status_code == 200
    session_id = r_upload.json()["data"]["session_id"]

    r_question = api_client.post(
        f"/sessions/{session_id}/questions",
        json={"question": "Who has the highest score?"},
    )
    assert r_question.status_code == 200
    body = r_question.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["answer"] is not None
    assert len(data["answer"]) > 0
    assert "Alice" in data["answer"] or "alice" in data["answer"].lower()
