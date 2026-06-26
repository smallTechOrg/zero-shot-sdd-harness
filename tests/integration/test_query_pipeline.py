"""Integration tests for POST /sessions/{id}/questions — requires real AGENT_GEMINI_API_KEY."""
import io
import pytest


def _upload_sales_csv(api_client) -> str:
    """Upload a small sales CSV and return the session_id."""
    csv_content = (
        "product_name,quantity,revenue\n"
        "Apple,10,99.99\n"
        "Banana,5,49.50\n"
        "Cherry,20,200.00\n"
        "Date,3,30.00\n"
        "Elderberry,8,80.00\n"
    )
    r = api_client.post(
        "/sessions",
        files={"file": ("sales.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    return r.json()["data"]["session_id"]


@pytest.mark.usefixtures("_require_gemini_key")
class TestAnalysisPipelineReal:
    def test_question_returns_200(self, api_client):
        session_id = _upload_sales_csv(api_client)
        r = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "What is the total revenue by product?"},
        )
        assert r.status_code == 200

    def test_question_returns_answer(self, api_client):
        session_id = _upload_sales_csv(api_client)
        r = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "Which product has the highest revenue?"},
        )
        data = r.json()["data"]
        assert data["answer"] is not None
        assert len(data["answer"]) > 10

    def test_question_returns_run_id(self, api_client):
        session_id = _upload_sales_csv(api_client)
        r = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "How many rows?"},
        )
        data = r.json()["data"]
        assert "run_id" in data
        assert len(data["run_id"]) > 10

    def test_chart_fields_are_null_in_phase1(self, api_client):
        """Phase 2 stub: chart_base64 and chart_type are None in Phase 1."""
        session_id = _upload_sales_csv(api_client)
        r = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "What is the total revenue?"},
        )
        data = r.json()["data"]
        assert data["chart_base64"] is None
        assert data["chart_type"] is None


class TestQuestionErrorCases:
    def test_session_not_found_returns_404(self, api_client):
        r = api_client.post(
            "/sessions/nonexistent-uuid-1234/questions",
            json={"question": "Test?"},
        )
        assert r.status_code == 404

    def test_empty_question_rejected(self, api_client):
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
