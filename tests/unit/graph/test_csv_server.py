"""Unit tests for the per-source DuckDB MCP server, exercised via the real in-memory
MCP client (no graph involved)."""
import asyncio

import pandas as pd
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from data_analysis_agent.graph.mcp.csv_server import build_server


def _source(tmp_path):
    pq = tmp_path / "sales.parquet"
    pd.DataFrame({"region": ["N", "S", "N"], "sales": [10, 20, 30]}).to_parquet(pq)
    return {"id": "ds1", "name": "sales.csv", "table_name": "ds_sales", "parquet_path": str(pq)}


async def _list_tools(server):
    async with create_connected_server_and_client_session(server) as session:
        listed = await session.list_tools()
        return [(t.name, t.inputSchema) for t in listed.tools]


async def _call(server, query):
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("run_query", {"query": query})
        return result.content[0].text, result.isError


def test_lists_a_run_query_tool_with_query_param(tmp_path):
    server = build_server(_source(tmp_path), "Run SQL against sales.")
    tools = asyncio.run(_list_tools(server))
    server._duckdb_conn.close()
    assert [name for name, _ in tools] == ["run_query"]
    assert "query" in tools[0][1]["properties"]


def test_select_returns_compact_csv(tmp_path):
    server = build_server(_source(tmp_path), "desc")
    text, is_error = asyncio.run(_call(server, "SELECT SUM(sales) AS s FROM ds_sales"))
    server._duckdb_conn.close()
    assert is_error is False
    assert text.strip() == "s\n60"


def test_native_duckdb_aggregates_work(tmp_path):
    server = build_server(_source(tmp_path), "desc")
    text, is_error = asyncio.run(_call(server, "SELECT STDDEV(sales) AS sd FROM ds_sales"))
    server._duckdb_conn.close()
    assert is_error is False
    assert text.startswith("sd\n")


def test_non_select_is_recoverable_error(tmp_path):
    server = build_server(_source(tmp_path), "desc")
    text, is_error = asyncio.run(_call(server, "DROP TABLE ds_sales"))
    server._duckdb_conn.close()
    assert is_error is True
    assert "Only SELECT" in text


def test_bad_sql_is_recoverable_error(tmp_path):
    server = build_server(_source(tmp_path), "desc")
    text, is_error = asyncio.run(_call(server, "SELECT nope FROM ds_sales"))
    server._duckdb_conn.close()
    assert is_error is True


def test_row_cap_is_enforced(tmp_path):
    pq = tmp_path / "big.parquet"
    pd.DataFrame({"n": range(50)}).to_parquet(pq)
    src = {"id": "b", "name": "big.csv", "table_name": "big", "parquet_path": str(pq)}
    server = build_server(src, "desc", max_rows=5)
    text, is_error = asyncio.run(_call(server, "SELECT n FROM big"))
    server._duckdb_conn.close()
    assert is_error is False
    assert len(text.splitlines()) == 1 + 5  # header + capped rows


def test_missing_parquet_raises(tmp_path):
    src = {"id": "x", "name": "x.csv", "table_name": "x", "parquet_path": str(tmp_path / "nope.parquet")}
    with pytest.raises(FileNotFoundError):
        build_server(src, "desc")
