"""Integration tests for POST /datasets upload endpoint."""
import io
import json
from pathlib import Path

import pytest


def test_upload_csv_returns_201(app_client, sample_csv):
    """Upload a valid CSV — expect 201 with correct metadata."""
    with open(sample_csv, "rb") as f:
        r = app_client.post(
            "/datasets",
            files={"file": ("sample.csv", f, "text/csv")},
            data={"name": "employees"},
        )
    assert r.status_code == 201
    body = r.json()
    assert "dataset_id" in body
    assert body["name"] == "employees"
    assert body["row_count"] == 20
    assert body["column_count"] == 5
    assert isinstance(body["schema"], list)
    assert len(body["schema"]) == 5
    # Verify column names present in schema
    col_names = {c["column"] for c in body["schema"]}
    assert "employee_id" in col_names
    assert "salary" in col_names


def test_upload_creates_sqlite_row(app_client, sample_csv):
    """Uploaded dataset must appear in the dataset list."""
    with open(sample_csv, "rb") as f:
        app_client.post(
            "/datasets",
            files={"file": ("sample.csv", f, "text/csv")},
            data={"name": "employees"},
        )
    r = app_client.get("/datasets")
    assert r.status_code == 200
    body = r.json()
    datasets = body.get("datasets", [])
    assert len(datasets) == 1
    assert datasets[0]["name"] == "employees"


def test_upload_empty_csv_header_only_returns_201(app_client, tmp_path):
    """CSV with header but zero data rows — upload should succeed with row_count=0."""
    csv_content = b"col_a,col_b,col_c\n"
    r = app_client.post(
        "/datasets",
        files={"file": ("empty.csv", io.BytesIO(csv_content), "text/csv")},
        data={"name": "empty_dataset"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["row_count"] == 0
    assert body["column_count"] == 3


def test_upload_truly_empty_file_returns_422(app_client):
    """A file with no content at all (no headers) must return 422."""
    r = app_client.post(
        "/datasets",
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        data={"name": "bad"},
    )
    assert r.status_code == 422


def test_upload_malformed_csv_returns_422(app_client):
    """A file with inconsistent column counts cannot be parsed and must return 422."""
    # CSV with mismatched column counts — pandas raises a tokenization error
    malformed = b"a,b,c\n1,2\n3,4,5,6,7\n8,9"
    r = app_client.post(
        "/datasets",
        files={"file": ("bad.csv", io.BytesIO(malformed), "text/csv")},
        data={"name": "garbage"},
    )
    assert r.status_code == 422


def test_upload_unsupported_extension_returns_415(app_client):
    """Non-CSV/Excel extension must return 415."""
    r = app_client.post(
        "/datasets",
        files={"file": ("data.txt", io.BytesIO(b"a,b\n1,2\n"), "text/plain")},
        data={"name": "bad_ext"},
    )
    assert r.status_code == 415


def test_upload_file_over_50mb_returns_413(app_client):
    """File exceeding 50 MB must return 413."""
    big_content = b"a,b,c\n" + b"1,2,3\n" * (10 * 1024 * 1024)  # ~50+ MB
    r = app_client.post(
        "/datasets",
        files={"file": ("big.csv", io.BytesIO(big_content), "text/csv")},
        data={"name": "huge"},
    )
    assert r.status_code == 413


def test_upload_with_description(app_client, sample_csv):
    """Description field is stored correctly."""
    with open(sample_csv, "rb") as f:
        r = app_client.post(
            "/datasets",
            files={"file": ("sample.csv", f, "text/csv")},
            data={"name": "employees", "description": "HR employee data"},
        )
    assert r.status_code == 201
    body = r.json()
    assert body["description"] == "HR employee data"


def test_upload_dataset_is_queryable_via_list(app_client, sample_csv, uploaded_dataset):
    """After upload, the dataset appears in GET /datasets with correct data."""
    r = app_client.get("/datasets")
    assert r.status_code == 200
    datasets = r.json()["datasets"]
    found = next((d for d in datasets if d["dataset_id"] == uploaded_dataset["dataset_id"]), None)
    assert found is not None
    assert found["row_count"] == 20
