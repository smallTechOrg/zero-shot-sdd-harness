"""Integration tests for POST /sessions — no LLM key required."""
import io
import json
import pytest


def _make_csv(headers: list, rows: list) -> io.BytesIO:
    lines = [",".join(str(h) for h in headers)]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    content = "\n".join(lines) + "\n"
    return io.BytesIO(content.encode("utf-8"))


class TestUploadSuccess:
    def test_returns_200(self, api_client):
        csv_buf = _make_csv(["name", "age"], [["Alice", "30"], ["Bob", "25"]])
        r = api_client.post(
            "/sessions",
            files={"file": ("people.csv", csv_buf, "text/csv")},
        )
        assert r.status_code == 200

    def test_response_has_session_id(self, api_client):
        csv_buf = _make_csv(["name", "age"], [["Alice", "30"]])
        r = api_client.post(
            "/sessions",
            files={"file": ("people.csv", csv_buf, "text/csv")},
        )
        data = r.json()["data"]
        assert "session_id" in data
        assert len(data["session_id"]) > 10

    def test_response_has_correct_row_count(self, api_client):
        csv_buf = _make_csv(["a", "b", "c"], [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]])
        r = api_client.post(
            "/sessions",
            files={"file": ("data.csv", csv_buf, "text/csv")},
        )
        assert r.json()["data"]["row_count"] == 3

    def test_response_columns_match_headers(self, api_client):
        csv_buf = _make_csv(["product", "quantity", "price"], [["Apple", "10", "1.99"]])
        r = api_client.post(
            "/sessions",
            files={"file": ("sales.csv", csv_buf, "text/csv")},
        )
        data = r.json()["data"]
        col_names = [c["name"] for c in data["columns"]]
        assert "product" in col_names
        assert "quantity" in col_names
        assert "price" in col_names

    def test_session_persisted_in_db(self, api_client, _isolated_db):
        csv_buf = _make_csv(["col1"], [["val1"]])
        r = api_client.post(
            "/sessions",
            files={"file": ("test_persist.csv", csv_buf, "text/csv")},
        )
        session_id = r.json()["data"]["session_id"]

        from sqlalchemy.orm import Session
        from db.models import SessionRow
        with Session(_isolated_db) as s:
            row = s.get(SessionRow, session_id)
        assert row is not None
        assert row.row_count == 1


class TestUploadErrors:
    def test_wrong_extension_returns_400(self, api_client):
        r = api_client.post(
            "/sessions",
            files={"file": ("data.txt", io.BytesIO(b"a,b\n1,2"), "text/plain")},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_CSV"

    def test_json_extension_returns_400(self, api_client):
        r = api_client.post(
            "/sessions",
            files={"file": ("data.json", io.BytesIO(b'{"a":1}'), "application/json")},
        )
        assert r.status_code == 400

    def test_empty_file_returns_400(self, api_client):
        csv_buf = io.BytesIO(b"")
        r = api_client.post(
            "/sessions",
            files={"file": ("empty.csv", csv_buf, "text/csv")},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_CSV"
