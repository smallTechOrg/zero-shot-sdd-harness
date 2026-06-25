"""Unit tests for the session pool with the single-level MCP-server model: flat snapshot, server
routing, within-server JOINs, reuse, LRU eviction, cleanup. Servers are stubbed (no DB) by patching
``_load_servers``; the in-process MCP servers + DuckDB are exercised for real."""
import asyncio

import pandas as pd
import pytest

import data_analysis_agent.tools.mcp.pool as pool_module
from data_analysis_agent.tools.mcp.pool import SessionPoolManager


def _server(tmp_path, name, tables_spec):
    """Build a (server_dict, tables_dicts) pair with real Parquet files."""
    tables = []
    for table_name, frame in tables_spec.items():
        pq = tmp_path / f"{name}__{table_name}.parquet"
        pd.DataFrame(frame).to_parquet(pq)
        tables.append({
            "table_name": table_name,
            "parquet_path": str(pq),
            "column_names": list(frame.keys()),
        })
    server = {"id": name, "name": name, "type": "parquet", "uri": f"parquet:///{name}",
              "description": f"Server {name}"}
    return server, tables


@pytest.fixture
def patch_servers(monkeypatch):
    """Return a mutable {session_id: [(server, tables), ...]} map, bypassing the DB."""
    mapping: dict[str, list] = {}
    monkeypatch.setattr(pool_module, "_load_servers", lambda sid: mapping.get(sid, []))
    return mapping


def test_snapshot_flat_and_single_level_routing(tmp_path, patch_servers):
    patch_servers["s1"] = [_server(tmp_path, "sales_db", {
        "orders": {"id": [1, 2, 3], "cust": [10, 10, 20], "amount": [5, 7, 3]},
        "customers": {"id": [10, 20], "region": ["N", "S"]},
    })]
    mgr = SessionPoolManager(8, 1000)

    async def body():
        await mgr.acquire("s1")
        snap = mgr.snapshot("s1")
        ok = await mgr.call_tool("s1", "sales_db", {
            "query": "SELECT c.region, SUM(o.amount) AS t FROM orders o JOIN customers c "
                     "ON o.cust = c.id GROUP BY c.region ORDER BY c.region"
        })
        bad = await mgr.call_tool("s1", "nope", {"query": "SELECT 1"})
        return snap, ok, bad

    snap, ok, bad = asyncio.run(body())
    assert len(snap) == 1 and snap[0]["tool"] == "sales_db"
    assert sorted(t["table"] for t in snap[0]["tables"]) == ["customers", "orders"]
    assert ok == ("region,t\nN,12\nS,3", False)            # within-server JOIN
    assert bad[1] is True and "Unknown tool" in bad[0]


def test_snapshot_carries_tables_and_columns(tmp_path, patch_servers):
    patch_servers["s1"] = [_server(tmp_path, "d", {"orders": {"id": [1], "total": [5]}})]
    mgr = SessionPoolManager(8, 1000)
    asyncio.run(mgr.acquire("s1"))
    snap = mgr.snapshot("s1")[0]
    assert snap["description"] == "Server d"
    assert snap["tables"][0] == {"table": "orders", "columns": ["id", "total"]}


def test_non_select_is_recoverable_error(tmp_path, patch_servers):
    patch_servers["s1"] = [_server(tmp_path, "d", {"t": {"x": [1]}})]
    mgr = SessionPoolManager(8, 1000)

    async def body():
        await mgr.acquire("s1")
        return await mgr.call_tool("s1", "d", {"query": "DROP TABLE t"})

    text, is_error = asyncio.run(body())
    assert is_error is True and "SELECT" in text


def test_acquire_reuses_pool(tmp_path, patch_servers):
    patch_servers["s1"] = [_server(tmp_path, "d", {"t": {"x": [1]}})]
    mgr = SessionPoolManager(8, 1000)

    async def body():
        return await mgr.acquire("s1") is await mgr.acquire("s1")

    assert asyncio.run(body()) is True


def test_no_servers_raises(patch_servers):
    mgr = SessionPoolManager(8, 1000)
    with pytest.raises(pool_module.NoServersError):
        asyncio.run(mgr.acquire("missing"))


def test_lru_eviction(tmp_path, patch_servers):
    for sid in ("s1", "s2", "s3"):
        patch_servers[sid] = [_server(tmp_path, f"d_{sid}", {"t": {"x": [1]}})]
    mgr = SessionPoolManager(max_pools=2, idle_seconds=1000)

    async def body():
        await mgr.acquire("s1")
        await mgr.acquire("s2")
        await mgr.acquire("s3")  # exceeds cap → evicts LRU (s1)

    asyncio.run(body())
    assert mgr.snapshot("s1") == []   # evicted
    assert mgr.snapshot("s2") and mgr.snapshot("s3")


def test_close_is_idempotent(tmp_path, patch_servers):
    patch_servers["s1"] = [_server(tmp_path, "d", {"t": {"x": [1]}})]
    mgr = SessionPoolManager(8, 1000)
    asyncio.run(mgr.acquire("s1"))
    mgr.close("s1")
    mgr.close("s1")  # must not raise
    assert mgr.snapshot("s1") == []
