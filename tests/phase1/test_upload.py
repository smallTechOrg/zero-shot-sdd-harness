"""Phase 1 — Upload endpoint tests."""
import io

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures — in-memory CSV / Excel bytes
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_csv_bytes() -> bytes:
    """Small 3-row, 3-column CSV."""
    df = pd.DataFrame({
        "age": [25, 30, 35],
        "score": [88.5, 92.0, 76.3],
        "name": ["Alice", "Bob", "Carol"],
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def simple_excel_bytes() -> bytes:
    """Small 3-row, 2-column Excel file."""
    df = pd.DataFrame({
        "revenue": [1000.0, 2000.0, 1500.0],
        "quarter": ["Q1", "Q2", "Q3"],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_upload_valid_csv(api_client, simple_csv_bytes):
    """POST /uploads with a valid CSV returns upload metadata."""
    response = api_client.post(
        "/uploads",
        files={"file": ("test.csv", simple_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["error"] is None
    data = body["data"]
    assert data["upload_id"]
    assert data["filename"] == "test.csv"
    assert data["row_count"] == 3
    assert data["col_count"] == 3
    col_names = [c["name"] for c in data["columns"]]
    assert "age" in col_names
    assert "score" in col_names
    assert "name" in col_names


def test_upload_invalid_file_type(api_client):
    """POST /uploads with a .txt file returns 400."""
    txt_bytes = b"hello world\nthis is text"
    response = api_client.post(
        "/uploads",
        files={"file": ("data.txt", txt_bytes, "text/plain")},
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_FILE_TYPE"


def test_upload_invalid_file_type_json(api_client):
    """POST /uploads with a .json file returns 400."""
    json_bytes = b'{"key": "value"}'
    response = api_client.post(
        "/uploads",
        files={"file": ("data.json", json_bytes, "application/json")},
    )
    assert response.status_code == 400, response.text


def test_list_uploads_includes_uploaded_file(api_client, simple_csv_bytes):
    """GET /uploads returns a list containing the just-uploaded file."""
    # Upload a file first
    upload_resp = api_client.post(
        "/uploads",
        files={"file": ("list_test.csv", simple_csv_bytes, "text/csv")},
    )
    assert upload_resp.status_code == 200
    upload_id = upload_resp.json()["data"]["upload_id"]

    # List uploads
    list_resp = api_client.get("/uploads")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["error"] is None
    ids = [u["upload_id"] for u in body["data"]]
    assert upload_id in ids


def test_list_uploads_empty_initially(api_client):
    """GET /uploads on a clean DB returns an empty list."""
    response = api_client.get("/uploads")
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["error"] is None


def test_upload_valid_excel(api_client, simple_excel_bytes):
    """POST /uploads with a valid Excel file returns correct metadata."""
    response = api_client.post(
        "/uploads",
        files={"file": ("report.xlsx", simple_excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["error"] is None
    data = body["data"]
    assert data["upload_id"]
    assert data["filename"] == "report.xlsx"
    assert data["row_count"] == 3
    assert data["col_count"] == 2
    col_names = [c["name"] for c in data["columns"]]
    assert "revenue" in col_names
    assert "quarter" in col_names


def test_upload_returns_dtype_info(api_client, simple_csv_bytes):
    """Columns in the response carry dtype information."""
    response = api_client.post(
        "/uploads",
        files={"file": ("typed.csv", simple_csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    columns = response.json()["data"]["columns"]
    dtype_map = {c["name"]: c["dtype"] for c in columns}
    # age and score are numeric; name is string
    assert dtype_map["age"] in ("integer", "float")
    assert dtype_map["score"] in ("integer", "float")
    assert dtype_map["name"] == "string"
