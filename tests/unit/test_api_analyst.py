"""Additional analyst API tests — no LLM key required."""
import io
import pytest
from fastapi.testclient import TestClient
from api import app


@pytest.fixture
def client(_isolated_db):
    with TestClient(app) as c:
        yield c


def test_upload_empty_csv_returns_422(client):
    """Uploading a CSV with headers but no rows returns 422."""
    csv_bytes = b"a,b\n"  # header only, no data
    r = client.post(
        "/datasets/upload",
        headers={"X-Session-ID": "some-session"},
        files={"file": ("empty.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 422


def test_upload_response_shape(client):
    """Upload response has expected keys."""
    session_id = "shape-test-11111111-1111-1111-1111-111111111111"
    csv_bytes = b"x,y\n1,2\n3,4\n"
    r = client.post(
        "/datasets/upload",
        headers={"X-Session-ID": session_id},
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    data = body["data"]
    for key in ("dataset_id", "session_id", "table_name", "original_filename", "row_count", "column_names"):
        assert key in data, f"Missing key: {key}"


def test_datasets_table_name_namespaced(client):
    """table_name must start with the session prefix."""
    session_id = "ns-test-11111111-1111-1111-1111-111111111111"
    prefix = session_id.replace("-", "_")
    csv_bytes = b"a,b\n1,2\n"
    r = client.post(
        "/datasets/upload",
        headers={"X-Session-ID": session_id},
        files={"file": ("myfile.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 200
    table_name = r.json()["data"]["table_name"]
    assert table_name.startswith(prefix + "_")
