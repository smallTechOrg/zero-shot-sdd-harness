"""
Integration tests — run against the real Gemini API.
Tests upload a real CSV, ask a NL question, assert SQL was generated and rows returned,
and assert the audit log entry was written.
"""
import pytest
import io
import csv
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import db.session as session_module
from db.models import Base, AuditLogRow
from config.settings import get_settings

# Test session IDs (valid UUIDs)
TEST_SESSION = "test-session-11111111-1111-1111-1111-111111111111"
TEST_SESSION_PREFIX = TEST_SESSION.replace("-", "_")


@pytest.fixture(autouse=True)
def _isolated_db_integration(tmp_path, monkeypatch):
    """Use an isolated SQLite DB for each integration test."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("AGENT_DATABASE_URL", db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)

    # Reset Gemini provider singleton
    import llm.providers.gemini as gmod
    gmod._provider = None

    yield engine

    engine.dispose()
    session_module._engine = None
    session_module._SessionLocal = None
    gmod._provider = None


@pytest.fixture(autouse=True)
def _require_gemini_key():
    """Skip if real Gemini key is not set."""
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("AGENT_GEMINI_API_KEY not set — required for integration tests")


def _make_test_csv() -> bytes:
    """Create a small test CSV in memory."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["product", "sales", "region"])
    writer.writeheader()
    writer.writerows([
        {"product": "Widget A", "sales": 100, "region": "North"},
        {"product": "Widget B", "sales": 200, "region": "South"},
        {"product": "Widget C", "sales": 150, "region": "North"},
        {"product": "Widget D", "sales": 300, "region": "East"},
    ])
    return output.getvalue().encode()


def _make_async_client(app):
    """Create an httpx AsyncClient for ASGI testing (compatible with httpx>=0.23)."""
    import httpx
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def test_upload_and_query_end_to_end():
    """Upload a CSV, ask a NL question, assert answer + audit log entry."""
    from api import app
    import asyncio

    async def run():
        async with _make_async_client(app) as client:
            # 1. Upload CSV
            csv_bytes = _make_test_csv()
            response = await client.post(
                "/datasets/upload",
                headers={"X-Session-ID": TEST_SESSION},
                files={"file": ("test_sales.csv", io.BytesIO(csv_bytes), "text/csv")},
            )
            assert response.status_code == 200, f"Upload failed: {response.text}"
            dataset = response.json()["data"]
            table_name = dataset["table_name"]
            assert table_name.startswith(TEST_SESSION_PREFIX)
            assert dataset["row_count"] == 4

            # 2. List datasets
            response = await client.get("/datasets", headers={"X-Session-ID": TEST_SESSION})
            assert response.status_code == 200
            datasets = response.json()["data"]
            assert len(datasets) >= 1
            assert any(d["table_name"] == table_name for d in datasets)

            # 3. Ask a NL question
            response = await client.post(
                "/query",
                headers={"X-Session-ID": TEST_SESSION},
                json={
                    "question": "How many rows are there in total?",
                    "dataset_table": table_name,
                },
            )
            assert response.status_code == 200, f"Query failed: {response.text}"
            result = response.json()["data"]
            assert "answer" in result
            assert result["answer"]  # non-empty
            assert "sql" in result
            assert result["sql"].strip().upper().startswith("SELECT")
            assert "audit_id" in result
            assert result["audit_id"]

            # 4. Check audit log
            response = await client.get("/audit", headers={"X-Session-ID": TEST_SESSION})
            assert response.status_code == 200
            audit_entries = response.json()["data"]
            assert len(audit_entries) >= 1
            entry = audit_entries[0]
            assert entry["session_id"] == TEST_SESSION
            assert entry["sql_generated"] is not None
            assert entry["row_count"] is not None
            assert entry["duration_ms"] is not None

    asyncio.run(run())


def test_cross_session_isolation():
    """A session cannot query another session's table."""
    from api import app
    import asyncio

    other_session = "other-session-22222222-2222-2222-2222-222222222222"

    async def run():
        async with _make_async_client(app) as client:
            # Upload to session 1
            csv_bytes = _make_test_csv()
            response = await client.post(
                "/datasets/upload",
                headers={"X-Session-ID": TEST_SESSION},
                files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
            )
            assert response.status_code == 200
            table_name = response.json()["data"]["table_name"]

            # Try to query from session 2
            response = await client.post(
                "/query",
                headers={"X-Session-ID": other_session},
                json={"question": "How many rows?", "dataset_table": table_name},
            )
            assert response.status_code == 403

    asyncio.run(run())


def test_upload_invalid_file_type():
    """Uploading a non-CSV/Excel file returns 422."""
    from api import app
    import asyncio

    async def run():
        async with _make_async_client(app) as client:
            response = await client.post(
                "/datasets/upload",
                headers={"X-Session-ID": TEST_SESSION},
                files={"file": ("bad.txt", io.BytesIO(b"not a csv"), "text/plain")},
            )
            assert response.status_code == 422

    asyncio.run(run())


def test_health():
    """Health endpoint returns 200."""
    from api import app
    import asyncio

    async def run():
        async with _make_async_client(app) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    asyncio.run(run())


def test_re_upload_replaces_dataset():
    """Re-uploading to the same session/filename replaces the existing dataset."""
    from api import app
    import asyncio

    async def run():
        async with _make_async_client(app) as client:
            csv1 = b"a,b\n1,2\n3,4\n"
            csv2 = b"a,b,c\n1,2,3\n"

            r1 = await client.post(
                "/datasets/upload",
                headers={"X-Session-ID": TEST_SESSION},
                files={"file": ("data.csv", io.BytesIO(csv1), "text/csv")},
            )
            assert r1.status_code == 200
            assert r1.json()["data"]["row_count"] == 2

            r2 = await client.post(
                "/datasets/upload",
                headers={"X-Session-ID": TEST_SESSION},
                files={"file": ("data.csv", io.BytesIO(csv2), "text/csv")},
            )
            assert r2.status_code == 200
            assert r2.json()["data"]["row_count"] == 1

            # Only one dataset row for this table
            r3 = await client.get("/datasets", headers={"X-Session-ID": TEST_SESSION})
            items = r3.json()["data"]
            table_name = r2.json()["data"]["table_name"]
            matching = [d for d in items if d["table_name"] == table_name]
            assert len(matching) == 1

    asyncio.run(run())
