"""FR-001 session persistence criteria.

Three tests:
1. Datasets registered in a session are queryable across HTTP requests (in-process)
2. DuckDB tables are queryable after a fresh DuckDB connection open (simulates restart)
3. GET /sessions/{id} returns full ordered conversation history as JSON array

Gate command: uv run --extra dev pytest tests/test_persistence_fr.py -v
"""
import json

import httpx
import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage, ToolMessage

from src.server import app
from src.runner import run_agent
from src import duck


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tc(name: str, args: dict, tid: str):
    return {"id": tid, "name": name, "args": args, "type": "tool_call"}


def _tool_msgs(messages) -> list[ToolMessage]:
    return [m for m in messages if isinstance(m, ToolMessage)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_datasets_persist_across_requests():
    """WHILE session active, all uploaded datasets SHALL be available without re-uploading."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        # Create dataset + upload file
        create_resp = await c.post("/datasets", json={"name": "persist_test"})
        assert create_resp.status_code == 200
        ds_id = create_resp.json()["data"]["id"]

        files = {"file": ("p.csv", "x,y\n1,10\n2,20\n3,30\n", "text/csv")}
        upload_resp = await c.post(f"/datasets/{ds_id}/files", files=files)
        assert upload_resp.status_code == 200

        # Multiple requests — dataset must remain queryable each time
        for _ in range(3):
            det_resp = await c.get(f"/datasets/{ds_id}")
            assert det_resp.status_code == 200
            det = det_resp.json()
            assert det["ok"], det
            assert any(t["table_name"] == "p" for t in det["data"]["tables"]), (
                f"table 'p' not found in {det['data']['tables']}"
            )


@pytest.mark.asyncio
async def test_duckdb_table_queryable_after_fresh_connection():
    """Simulate restart: open a fresh DuckDB read-only connection and verify table is still there."""
    transport = httpx.ASGITransport(app=app)
    # Upload via API first
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        create_resp = await c.post("/datasets", json={"name": "restart_test"})
        assert create_resp.status_code == 200
        ds_id = create_resp.json()["data"]["id"]

        files = {"file": ("r.csv", "col,val\nA,100\nB,200\n", "text/csv")}
        upload_resp = await c.post(f"/datasets/{ds_id}/files", files=files)
        assert upload_resp.status_code == 200

    # Now open a fresh DuckDB connection (as if the server restarted).
    # duck.run_query() always opens a new read_only connection — simulates what happens
    # when the server process restarts and re-reads from disk.
    result = duck.run_query(
        ds_id,
        'SELECT col, val FROM "r" ORDER BY val DESC',
        max_rows=10,
    )
    assert not result.get("error"), f"DuckDB query failed after fresh connection: {result.get('error')}"
    assert result["row_count"] == 2, f"Expected 2 rows, got {result['row_count']}"
    assert result["rows"][0][1] == 200, f"Expected first row val=200 (B), got {result['rows'][0]}"


@pytest.mark.asyncio
async def test_session_history_returned_as_json_array():
    """WHEN server restarts and client reconnects, GET /sessions/{id} SHALL return ordered history."""
    thread_id = "persist-session-001"

    # Seed a dataset for the agent to use
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        create_resp = await c.post("/datasets", json={"name": "history_test"})
        assert create_resp.status_code == 200
        ds_id = create_resp.json()["data"]["id"]

        files = {"file": ("h.csv", "name,score\nAlice,95\nBob,87\n", "text/csv")}
        upload_resp = await c.post(f"/datasets/{ds_id}/files", files=files)
        assert upload_resp.status_code == 200

    # FakeModel: executes one SQL query then finishes — mirrors pattern from test_query_fr.py
    class _SimpleModel:
        def __init__(self, ds_id: str, table: str, sql: str):
            self._ds_id = ds_id
            self._table = table
            self._sql = sql

        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            n = len(_tool_msgs(messages))
            if n == 0:
                return AIMessage(content="", tool_calls=[
                    _tc("execute_sql", {"dataset_id": self._ds_id, "sql": self._sql}, "t1"),
                ])
            # Parse result and build Markdown table
            last_tm = _tool_msgs(messages)[-1]
            try:
                data = json.loads(last_tm.content)
            except Exception:
                data = {}
            rows = data.get("rows", [])
            cols = data.get("columns", ["name", "score"])
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join("---" for _ in cols) + " |"
            body_lines = ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
            md_table = "\n".join([header, sep] + body_lines)
            return AIMessage(content="", tool_calls=[
                _tc("finish", {"answer": f"Results:\n\n{md_table}"}, "t2"),
            ])

    goals = ["What are the scores?", "Who scored highest?"]
    for goal in goals:
        model = _SimpleModel(
            ds_id, "h",
            f'SELECT name, score FROM "h" ORDER BY score DESC LIMIT 2',
        )
        result = await run_agent(
            goal=goal,
            dataset_id=ds_id,
            thread_id=thread_id,
            model=model,
        )
        assert result["status"] == "completed", f"run_agent failed for goal {goal!r}: {result}"

    # GET /sessions/{thread_id} — verify 2 runs in chronological order
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(f"/sessions/{thread_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"], f"Expected ok=true, got: {body}"

    runs = body["data"]["runs"]
    assert len(runs) == 2, f"Expected 2 runs, got {len(runs)}: {runs}"
    assert runs[0]["goal"] == "What are the scores?", f"First run goal mismatch: {runs[0]['goal']!r}"
    assert runs[1]["goal"] == "Who scored highest?", f"Second run goal mismatch: {runs[1]['goal']!r}"
    assert runs[0]["created_at"] <= runs[1]["created_at"], (
        f"Runs not in chronological order: {runs[0]['created_at']} > {runs[1]['created_at']}"
    )
