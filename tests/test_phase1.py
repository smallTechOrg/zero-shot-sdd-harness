"""Phase 1 integration tests — real Gemini API calls.

Requires AGENT_GEMINI_API_KEY in .env.
"""
import io
import pytest


def _make_people_csv() -> bytes:
    lines = [
        "name,age,city",
        "Alice,30,New York",
        "Bob,25,Chicago",
        "Carol,35,Los Angeles",
        "Dave,28,Houston",
        "Eve,32,Phoenix",
        "Frank,27,Philadelphia",
        "Grace,31,San Antonio",
        "Hank,29,San Diego",
        "Iris,33,Dallas",
        "Jack,26,San Jose",
    ]
    return "\n".join(lines).encode("utf-8")


@pytest.mark.usefixtures("_require_gemini_key")
class TestUploadSession:
    def test_upload_returns_session_id(self, api_client):
        csv_bytes = _make_people_csv()
        r = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert "session_id" in data
        assert len(data["session_id"]) == 36  # UUID

    def test_upload_returns_correct_row_count(self, api_client):
        csv_bytes = _make_people_csv()
        r = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["row_count"] == 10

    def test_upload_returns_columns(self, api_client):
        csv_bytes = _make_people_csv()
        r = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()["data"]
        col_names = [c["name"] for c in data["columns"]]
        assert "name" in col_names
        assert "age" in col_names
        assert "city" in col_names

    def test_upload_returns_dtypes(self, api_client):
        csv_bytes = _make_people_csv()
        r = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        data = r.json()["data"]
        # Each column entry has name + dtype
        for col in data["columns"]:
            assert "name" in col
            assert "dtype" in col


@pytest.mark.usefixtures("_require_gemini_key")
class TestAskQuestion:
    def test_question_returns_answer(self, api_client):
        csv_bytes = _make_people_csv()
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        r_question = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "how many rows does this dataset have?"},
        )
        assert r_question.status_code == 200
        data = r_question.json()["data"]
        assert data["answer"] is not None
        assert len(data["answer"]) > 0

    def test_question_answer_contains_row_count(self, api_client):
        """Gemini must mention '10' when asked how many rows the 10-row dataset has."""
        csv_bytes = _make_people_csv()
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        r_question = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "how many rows does this dataset have?"},
        )
        data = r_question.json()["data"]
        assert "10" in data["answer"], f"Expected '10' in answer: {data['answer']}"

    def test_question_returns_run_id(self, api_client):
        csv_bytes = _make_people_csv()
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        r_question = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "What are the column names?"},
        )
        data = r_question.json()["data"]
        assert "run_id" in data
        assert len(data["run_id"]) == 36  # UUID

    def test_question_returns_observability(self, api_client):
        """tokens_in, tokens_out, latency_ms should be populated."""
        csv_bytes = _make_people_csv()
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        r_question = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": "What city is Alice from?"},
        )
        data = r_question.json()["data"]
        assert data["tokens_in"] is not None and data["tokens_in"] > 0
        assert data["tokens_out"] is not None and data["tokens_out"] > 0
        assert data["latency_ms"] is not None and data["latency_ms"] > 0


class TestUploadErrors:
    def test_empty_file_returns_400(self, api_client):
        r = api_client.post(
            "/sessions",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert r.status_code == 400

    def test_non_csv_returns_400(self, api_client):
        r = api_client.post(
            "/sessions",
            files={"file": ("data.txt", io.BytesIO(b"hello world"), "text/plain")},
        )
        assert r.status_code == 400

    def test_json_file_returns_400(self, api_client):
        r = api_client.post(
            "/sessions",
            files={"file": ("data.json", io.BytesIO(b'{"a": 1}'), "application/json")},
        )
        assert r.status_code == 400


class TestQuestionErrors:
    def test_invalid_session_returns_404(self, api_client):
        r = api_client.post(
            "/sessions/nonexistent-session-id/questions",
            json={"question": "What are the columns?"},
        )
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "SESSION_NOT_FOUND"

    def test_empty_question_returns_400(self, api_client):
        # First upload a valid CSV so session exists in memory
        csv_bytes = _make_people_csv()
        r_upload = api_client.post(
            "/sessions",
            files={"file": ("people.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        session_id = r_upload.json()["data"]["session_id"]

        r = api_client.post(
            f"/sessions/{session_id}/questions",
            json={"question": ""},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "EMPTY_QUESTION"
