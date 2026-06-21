import os
import tempfile
import pytest
from src.config import get_settings


@pytest.fixture(autouse=True)
def _offline_guard(monkeypatch, tmp_path):
    """Force stub mode; point DB files at temp dirs so tests never write ./data/."""
    monkeypatch.setenv("DAA_LLM_PROVIDER", "stub")
    monkeypatch.setenv("DAA_DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("DAA_SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ALLOW_MODEL_REQUESTS", "False")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client():
    from httpx import AsyncClient, ASGITransport
    from src.api.main import create_app
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
