import pytest
from httpx import AsyncClient, ASGITransport
import src.api.main as main_mod
from src.db.sqlite import create_tables_sqlite


@pytest.fixture
async def client(tmp_path, monkeypatch):
    from src.config import get_settings
    monkeypatch.setenv("DAA_SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("DAA_DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    get_settings.cache_clear()
    from src.api.main import create_app
    app = create_app()
    await create_tables_sqlite()
    main_mod._ready = True
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    main_mod._ready = False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_create_and_list_session(client):
    """P1-AC10: POST /sessions → 201 + uuid4 id + Location header; GET /sessions lists it."""
    r = await client.post("/sessions")
    assert r.status_code == 201, r.text
    body = r.json()
    session_id = body["id"]
    # uuid4 format: 36 chars with 4 hyphens
    assert len(session_id) == 36
    assert session_id.count("-") == 4
    # Location header
    assert "Location" in r.headers
    assert session_id in r.headers["Location"]

    # List sessions — must include the new one
    r2 = await client.get("/sessions")
    assert r2.status_code == 200
    sessions = r2.json()["sessions"]
    assert any(s["id"] == session_id for s in sessions)


@pytest.mark.asyncio
async def test_session_persists(client):
    """P1-AC10 extra: session retrievable by GET /sessions/{id}."""
    r = await client.post("/sessions")
    session_id = r.json()["id"]
    r2 = await client.get(f"/sessions/{session_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == session_id


@pytest.mark.asyncio
async def test_history_returns_404_in_phase1(client):
    """Phase 1 deferred stub: GET /sessions/{id}/history returns 404."""
    r = await client.post("/sessions")
    session_id = r.json()["id"]
    r2 = await client.get(f"/sessions/{session_id}/history")
    assert r2.status_code == 404
