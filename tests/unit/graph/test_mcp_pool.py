"""Unit tests for the per-run MCP client pool: namespacing, routing, descriptions,
and cleanup — exercised end-to-end through the real in-memory MCP transport."""
import asyncio

import pandas as pd

from data_analysis_agent.graph.mcp_pool import close_pool, get_pool, open_pool


def _source(tmp_path, name, table, frame):
    pq = tmp_path / f"{table}.parquet"
    pd.DataFrame(frame).to_parquet(pq)
    return {
        "id": table,
        "name": name,
        "table_name": table,
        "parquet_path": str(pq),
        "capability_description": f"Query {name}",
    }


def test_two_sources_namespaced_tools_and_routing(tmp_path):
    s1 = _source(tmp_path, "sales.csv", "ds_sales", {"region": ["N", "S"], "sales": [10, 20]})
    s2 = _source(tmp_path, "cust.csv", "ds_cust", {"name": ["a", "b", "c"]})

    async def body():
        pool = await open_pool("run-1", [s1, s2])
        tools = pool.list_tools()
        sales = await pool.call_tool("ds_sales__run_query", {"query": "SELECT SUM(sales) AS s FROM ds_sales"})
        cust = await pool.call_tool("ds_cust__run_query", {"query": "SELECT COUNT(*) AS c FROM ds_cust"})
        unknown = await pool.call_tool("nope__run_query", {"query": "SELECT 1"})
        present = get_pool("run-1") is not None
        await close_pool("run-1")
        return tools, sales, cust, unknown, present

    tools, sales, cust, unknown, present = asyncio.run(body())

    assert sorted(t["name"] for t in tools) == ["ds_cust__run_query", "ds_sales__run_query"]
    assert present is True
    assert sales == ("s\n30", False)
    assert cust == ("c\n3", False)
    assert unknown[1] is True and "Unknown tool" in unknown[0]
    assert get_pool("run-1") is None  # closed + forgotten


def test_capability_description_becomes_tool_description(tmp_path):
    s1 = _source(tmp_path, "sales.csv", "ds_sales", {"sales": [1, 2]})

    async def body():
        pool = await open_pool("run-2", [s1])
        tools = pool.list_tools()
        await close_pool("run-2")
        return tools

    tools = asyncio.run(body())
    assert tools[0]["description"] == "Query sales.csv"
    assert "query" in tools[0]["parameter_schema"]


def test_close_pool_is_idempotent(tmp_path):
    s1 = _source(tmp_path, "sales.csv", "ds_sales", {"sales": [1, 2]})

    async def body():
        await open_pool("run-3", [s1])
        await close_pool("run-3")
        await close_pool("run-3")  # second call must not raise
        return True

    assert asyncio.run(body()) is True
