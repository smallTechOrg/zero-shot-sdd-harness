"""End-to-end tests — require real AGENT_GEMINI_API_KEY."""
import io
import pytest


@pytest.fixture
def sales_csv_bytes():
    content = (
        "product_name,quantity,revenue\n"
        "Apple,10,99.99\n"
        "Banana,5,49.50\n"
        "Cherry,20,200.00\n"
        "Date,3,30.00\n"
        "Elderberry,8,80.00\n"
    )
    return content.encode("utf-8")


@pytest.mark.usefixtures("_require_gemini_key")
class TestGoldenPath:
    def test_upload_then_question_full_pipeline(self, api_client, sales_csv_bytes):
        # Step 1: Upload CSV
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("sales.csv", io.BytesIO(sales_csv_bytes), "text/csv")},
        )
        assert r_upload.status_code == 200
        session_id = r_upload.json()["data"]["session_id"]

        # Step 2: Ask a natural-language question
        r_question = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "Which product has the highest revenue?"},
        )
        assert r_question.status_code == 200
        data = r_question.json()["data"]

        # Answer must be populated with a substantive response
        assert data["answer"] is not None, f"Expected answer, got: {data}"
        assert len(data["answer"]) > 10, "Answer should be substantive"
        assert data["run_id"] is not None

        # Phase 1: charts are Phase 2 stubs — must be null
        assert data["chart_base64"] is None, "Charts are Phase 2 (stub)"
        assert data["chart_type"] is None, "Charts are Phase 2 (stub)"

    def test_cherry_has_highest_revenue(self, api_client, sales_csv_bytes):
        """Gemini must identify Cherry (revenue 200.00) as highest."""
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("sales.csv", io.BytesIO(sales_csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        r_question = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "Which product has the highest revenue?"},
        )
        answer = r_question.json()["data"]["answer"].lower()
        assert "cherry" in answer, f"Expected 'cherry' in answer: {answer}"

    def test_run_id_is_uuid_like(self, api_client, sales_csv_bytes):
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("sales.csv", io.BytesIO(sales_csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        r_question = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "How many products are there?"},
        )
        data = r_question.json()["data"]
        run_id = data["run_id"]
        assert len(run_id) == 36  # UUID length with hyphens

    def test_multiple_questions_same_session(self, api_client, sales_csv_bytes):
        """Same session can handle multiple independent questions."""
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("sales.csv", io.BytesIO(sales_csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        questions = [
            "What is the total revenue?",
            "Which product has the highest quantity?",
        ]
        run_ids = []
        for q in questions:
            r = api_client.post(
                f"/sessions/{session_id}/questions",
                json={"question": q},
            )
            assert r.status_code == 200
            data = r.json()["data"]
            assert data["answer"] is not None
            run_ids.append(data["run_id"])

        # Each question should get a unique run_id
        assert len(set(run_ids)) == len(questions)
