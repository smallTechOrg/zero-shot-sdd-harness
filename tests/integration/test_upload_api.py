import io
import pytest


CSV_CONTENT = b"name,value\nAlice,10\nBob,20\nCarol,30\n"


def _create_session(client):
    resp = client.post("/sessions", json={})
    return resp.json()["data"]["session_id"]


def test_upload_csv_happy_path(client):
    sid = _create_session(client)
    resp = client.post(
        f"/sessions/{sid}/upload",
        files={"file": ("test.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["row_count"] == 3
    assert data["file_format"] == "csv"
    assert data["original_filename"] == "test.csv"
    assert "table_name" in data
    assert data["session_id"] == sid


def test_upload_unsupported_format(client):
    sid = _create_session(client)
    resp = client.post(
        f"/sessions/{sid}/upload",
        files={"file": ("test.xlsx", io.BytesIO(b"data"), "application/octet-stream")},
    )
    assert resp.status_code == 415


def test_upload_session_not_found(client):
    resp = client.post(
        "/sessions/nonexistent/upload",
        files={"file": ("test.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
    )
    assert resp.status_code == 404


def test_upload_large_file_rejected(client, monkeypatch):
    import data_analyst.api.upload as upload_module
    monkeypatch.setattr(upload_module, "_MAX_BYTES", 10)
    sid = _create_session(client)
    resp = client.post(
        f"/sessions/{sid}/upload",
        files={"file": ("big.csv", io.BytesIO(b"x" * 100), "text/csv")},
    )
    assert resp.status_code == 413


def test_upload_appears_in_dataset_list(client):
    sid = _create_session(client)
    client.post(
        f"/sessions/{sid}/upload",
        files={"file": ("data.csv", io.BytesIO(CSV_CONTENT), "text/csv")},
    )
    resp = client.get(f"/sessions/{sid}/datasets")
    assert resp.status_code == 200
    datasets = resp.json()["data"]
    assert len(datasets) == 1
    assert datasets[0]["original_filename"] == "data.csv"
