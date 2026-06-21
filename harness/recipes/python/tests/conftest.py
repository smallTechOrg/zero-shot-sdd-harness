import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
import src.db.session as _session_module


@pytest.fixture(autouse=True)
async def _use_test_db(monkeypatch, tmp_path):
    """Swap in a fresh SQLite DB for every test.

    For integration tests that need PostgreSQL behaviour (e.g. JSON columns,
    full-text search), set DATABASE_URL_TEST and use a real PostgreSQL instance.
    Override this fixture in tests/integration/conftest.py.
    """
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(_session_module, "AsyncSessionLocal", factory)

    async def _noop():
        pass

    monkeypatch.setattr(_session_module, "init_db", _noop)

    yield

    await engine.dispose()
