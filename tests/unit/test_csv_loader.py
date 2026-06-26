"""Unit tests for POST /sessions CSV parsing — no LLM key required."""
import io
import pytest


def _make_csv(headers: list, rows: list) -> io.BytesIO:
    lines = [",".join(str(h) for h in headers)]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    content = "\n".join(lines) + "\n"
    return io.BytesIO(content.encode("utf-8"))


class TestSessionUploadSuccess:
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

    def test_response_columns_have_dtype(self, api_client):
        csv_buf = _make_csv(["name", "count"], [["Alice", "5"]])
        r = api_client.post(
            "/sessions",
            files={"file": ("counts.csv", csv_buf, "text/csv")},
        )
        cols = r.json()["data"]["columns"]
        count_col = next(c for c in cols if c["name"] == "count")
        assert "dtype" in count_col
        # pandas infers int64
        assert "int" in count_col["dtype"]

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

    def test_dataframe_stored_in_memory(self, api_client):
        import sessions.store as store
        csv_buf = _make_csv(["x"], [["1"], ["2"]])
        r = api_client.post(
            "/sessions",
            files={"file": ("data.csv", csv_buf, "text/csv")},
        )
        session_id = r.json()["data"]["session_id"]
        df = store.get(session_id)
        assert df is not None
        assert len(df) == 2


class TestSessionUploadErrors:
    def test_non_csv_extension_returns_400(self, api_client):
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
        r = api_client.post(
            "/sessions",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_CSV"
