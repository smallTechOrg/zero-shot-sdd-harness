"""FR-001 audit log criteria — one test per EARS criterion.

Gate command: uv run --extra dev pytest tests/test_audit_fr.py -v
"""
import csv as csv_mod
import json
import os
import tempfile

import httpx
import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, ToolMessage

from src.runner import run_agent
from src.server import app


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _tc(name: str, args: dict, tid: str):
    return {"id": tid, "name": name, "args": args, "type": "tool_call"}


def _tool_msgs(messages) -> list[ToolMessage]:
    return [m for m in messages if isinstance(m, ToolMessage)]


@pytest_asyncio.fixture
async def seeded_dataset():
    """Upload a tiny CSV → DuckDB; return (dataset_id, table_name)."""
    from src.domain import Dataset, DataTable
    from src.db import get_sessionmaker
    from src import duck

    ds = Dataset(name="audit_test_sales")
    async with get_sessionmaker()() as s:
        s.add(ds)
        await s.commit()
        ds_id = ds.id

    rows = [
        ["product", "units", "price"],
        ["Widget", 10, 5.0],
        ["Gadget", 3, 20.0],
        ["Doohickey", 7, 12.5],
    ]
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as f:
        csv_mod.writer(f).writerows(rows)
        tmp = f.name

    import asyncio
    try:
        meta = await asyncio.to_thread(duck.ingest_file, ds_id, "sales.csv", tmp, "sales.csv")
    finally:
        os.unlink(tmp)

    async with get_sessionmaker()() as s:
        s.add(DataTable(
            dataset_id=ds_id,
            table_name=meta["table_name"],
            filename=meta["filename"],
            n_rows=meta["n_rows"],
            n_cols=meta["n_cols"],
            columns=meta["columns"],
        ))
        await s.commit()

    return ds_id, meta["table_name"]


def _make_sql_model(ds_id: str, table: str):
    """FakeModel that issues exactly one execute_sql call then finishes."""

    class _SqlModel:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            tms = _tool_msgs(messages)
            if len(tms) == 0:
                return AIMessage(content="", tool_calls=[
                    _tc("execute_sql", {
                        "dataset_id": ds_id,
                        "sql": f"SELECT product, units FROM {table} ORDER BY units DESC",
                    }, "t1")])
            return AIMessage(content="", tool_calls=[
                _tc("finish", {"answer": "Done."}, "t2")])

    return _SqlModel()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_written_per_sql_execution(seeded_dataset):
    """The system SHALL write one audit log entry per SQL execution."""
    ds_id, table = seeded_dataset

    result = await run_agent(
        goal="Show me product units",
        dataset_id=ds_id,
        model=_make_sql_model(ds_id, table),
    )
    thread_id = result["thread_id"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/sessions/{thread_id}/audit")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True, f"Unexpected error: {body}"
    entries = body["data"]
    assert len(entries) >= 1, "Expected at least one audit log entry after execute_sql"

    entry = entries[0]
    required_fields = {
        "timestamp", "session_id", "natural_language_query", "generated_sql",
        "rows_returned", "duration_ms", "prompt_tokens", "completion_tokens",
    }
    missing = required_fields - entry.keys()
    assert not missing, f"Audit entry missing fields: {missing}"

    assert entry["session_id"] == thread_id
    assert entry["natural_language_query"] == "Show me product units"
    assert "SELECT" in entry["generated_sql"].upper()


@pytest.mark.asyncio
async def test_audit_log_ordered_by_timestamp(seeded_dataset):
    """WHEN user requests audit log, system SHALL return entries ordered by timestamp ascending."""
    ds_id, table = seeded_dataset

    class _TwoSqlModel:
        """Issues two execute_sql calls then finishes."""

        def __init__(self):
            self._calls = 0

        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            tms = _tool_msgs(messages)
            n = len(tms)
            if n == 0:
                return AIMessage(content="", tool_calls=[
                    _tc("execute_sql", {
                        "dataset_id": ds_id,
                        "sql": f"SELECT COUNT(*) FROM {table}",
                    }, "t1")])
            if n == 1:
                return AIMessage(content="", tool_calls=[
                    _tc("execute_sql", {
                        "dataset_id": ds_id,
                        "sql": f"SELECT product FROM {table} ORDER BY price DESC LIMIT 1",
                    }, "t2")])
            return AIMessage(content="", tool_calls=[
                _tc("finish", {"answer": "Two queries done."}, "t3")])

    result = await run_agent(
        goal="Count rows then find most expensive product",
        dataset_id=ds_id,
        model=_TwoSqlModel(),
    )
    thread_id = result["thread_id"]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/sessions/{thread_id}/audit")

    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 2, f"Expected >=2 audit entries for two SQL calls, got {len(entries)}"

    timestamps = [e["timestamp"] for e in entries]
    assert timestamps == sorted(timestamps), (
        f"Audit entries not in ascending timestamp order: {timestamps}"
    )


@pytest.mark.asyncio
async def test_audit_log_empty_for_unknown_session():
    """WHEN session has no SQL executions, audit endpoint SHALL return empty list."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/sessions/nonexistent-session-xyz/audit")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"] == []


@pytest.mark.asyncio
async def test_audit_log_session_isolation(seeded_dataset):
    """WHEN two sessions run, each session's audit log MUST contain only its own entries."""
    ds_id, table = seeded_dataset

    result_a = await run_agent(
        goal="Session A query",
        dataset_id=ds_id,
        model=_make_sql_model(ds_id, table),
        thread_id="session-a-isolation-test",
    )
    result_b = await run_agent(
        goal="Session B query",
        dataset_id=ds_id,
        model=_make_sql_model(ds_id, table),
        thread_id="session-b-isolation-test",
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp_a = await client.get("/sessions/session-a-isolation-test/audit")
        resp_b = await client.get("/sessions/session-b-isolation-test/audit")

    entries_a = resp_a.json()["data"]
    entries_b = resp_b.json()["data"]

    assert all(e["session_id"] == "session-a-isolation-test" for e in entries_a), (
        "Session A audit contains entries from another session"
    )
    assert all(e["session_id"] == "session-b-isolation-test" for e in entries_b), (
        "Session B audit contains entries from another session"
    )
    assert len(entries_a) >= 1
    assert len(entries_b) >= 1
