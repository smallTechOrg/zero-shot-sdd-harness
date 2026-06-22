"""Integration test fixtures — isolated SQLite DB, isolated DuckDB, real Gemini API."""
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Load .env so GEMINI_API_KEY is available in os.environ for tests
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """
    Full FastAPI test client with isolated SQLite and DuckDB per test.
    Resets all singletons so each test starts clean.
    """
    db_path = tmp_path / "test.db"
    duckdb_path = tmp_path / "test.duckdb"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    # Patch env vars before anything imports settings
    monkeypatch.setenv("DA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DA_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("DA_UPLOAD_DIR", str(upload_dir))

    # Reset all singletons
    import data_analyst.config.settings as settings_mod
    import data_analyst.db.session as session_mod
    import data_analyst.duckdb_service as duckdb_mod

    settings_mod._settings = None
    session_mod._engine = None
    session_mod._SessionLocal = None
    duckdb_mod._duckdb_service = None

    from data_analyst.api import create_app
    app = create_app()

    with TestClient(app) as client:
        yield client

    # Cleanup singletons after test
    settings_mod._settings = None
    session_mod._engine = None
    session_mod._SessionLocal = None
    duckdb_mod._duckdb_service = None


@pytest.fixture()
def sample_csv() -> Path:
    """Return path to the sample CSV fixture."""
    return Path(__file__).parent.parent / "fixtures" / "sample.csv"


@pytest.fixture()
def uploaded_dataset(app_client, sample_csv):
    """Upload sample.csv and return the response body dict."""
    with open(sample_csv, "rb") as f:
        r = app_client.post(
            "/datasets",
            files={"file": ("sample.csv", f, "text/csv")},
            data={"name": "employees"},
        )
    assert r.status_code == 201, f"Upload failed: {r.text}"
    return r.json()
