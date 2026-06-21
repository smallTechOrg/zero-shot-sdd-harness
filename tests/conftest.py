"""Test harness — same async engine as prod, throwaway DB, fresh tables per test.

Set APP_DATABASE_URL + APP_DATA_DIR BEFORE importing src.db (the engine is built at import time).
FakeModel drives the ReAct loop offline (no API key) — harness/patterns/react-agent.md.
"""
import os
import tempfile

os.environ["APP_DATABASE_URL"] = "sqlite+aiosqlite:///./test_agent.db"
os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="analyst_test_"))
# Force offline: clear the key so _NEEDS_KEY tests skip and no real API calls are made.
# Run with APP_ANALYST_REAL_RUN=1 to opt into the live-key tests.
if not os.environ.get("APP_ANALYST_REAL_RUN"):
    os.environ["APP_LLM_API_KEY"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

import src.domain  # noqa: E402,F401 — register domain tables on Base before create_all
from src.db import Base, engine  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class FakeModel:
    """Scripted, no-key model: returns each scripted message in turn, clamping at the last."""

    def __init__(self, scripted):
        self.s = list(scripted)
        self.i = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        m = self.s[min(self.i, len(self.s) - 1)]
        self.i += 1
        return m


@pytest.fixture
def FakeModelCls():
    return FakeModel
