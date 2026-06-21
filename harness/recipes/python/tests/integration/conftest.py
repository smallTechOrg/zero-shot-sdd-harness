"""Integration test DB fixture — uses a real PostgreSQL instance.

Requires DATABASE_URL_TEST env var pointing to a dedicated test database.
Run: uv run pytest tests/integration/
"""

import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.base import Base
import src.db.session as _session_module

TEST_DB_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+asyncpg://user:password@localhost:5432/appname_test",
)


@pytest.fixture(autouse=True)
async def _use_postgres_test_db(monkeypatch):
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(_session_module, "AsyncSessionLocal", factory)

    async def _noop():
        pass

    monkeypatch.setattr(_session_module, "init_db", _noop)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
