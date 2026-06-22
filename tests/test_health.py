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
async def test_health_stub_offline(client):
    """P1-AC2: GET /health returns 200 with stub_mode:true in stub mode, no network."""
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["stub_mode"] is True
    assert body["llm_provider"] == "stub"
