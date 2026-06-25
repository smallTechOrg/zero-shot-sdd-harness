"""Unit tests for the connector seam: DatasetURI (credential-free display) and the ParquetConnector
(connection-check + build a server with a generic ``query`` tool and within-server JOINs), exercised
through the real in-memory MCP client."""
import asyncio

import pandas as pd
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from data_analysis_agent.tools.connectors.base import DatasetConnectionError, get_connector
from data_analysis_agent.tools.connectors.parquet import ParquetConnector
from data_analysis_agent.tools.connectors.uri import DatasetURI


def test_uri_internal_parquet():
    u = DatasetURI("parquet:///Q2%20Sales")
    assert u.scheme == "parquet"
    assert u.is_internal is True
    assert u.database == "Q2 Sales"       # URL-decoded
    assert u.host is None and u.username is None and u.has_password is False
    assert u.display() == "parquet:///Q2%20Sales"


def test_uri_external_strips_credentials():
    u = DatasetURI("postgresql://analyst:secret@db.internal:5432/sales")
    assert u.scheme == "postgresql"
    assert u.host == "db.internal" and u.port == 5432
    assert u.username == "analyst" and u.has_password is True
    assert u.database == "sales"
    shown = u.display()
    assert shown == "postgresql://db.internal:5432/sales"
    assert "secret" not in shown and "analyst" not in shown  # credentials never displayed


def _two_table_server(tmp_path):
    (tmp_path / "d").mkdir()
    orders = tmp_path / "d" / "orders.parquet"
    customers = tmp_path / "d" / "customers.parquet"
    pd.DataFrame({"id": [1, 2, 3], "cust": [10, 10, 20], "amount": [5, 7, 3]}).to_parquet(orders)
    pd.DataFrame({"id": [10, 20], "region": ["N", "S"]}).to_parquet(customers)
    server = {"name": "sales_db", "type": "parquet", "uri": "parquet:///sales_db"}
    tables = [
        {"table_name": "orders", "parquet_path": str(orders)},
        {"table_name": "customers", "parquet_path": str(customers)},
    ]
    return server, tables


def test_parquet_connection_check_ok_and_missing(tmp_path):
    server, tables = _two_table_server(tmp_path)
    ParquetConnector(server, tables).connection_check()  # no raise

    broken = [{"table_name": "x", "parquet_path": str(tmp_path / "nope.parquet")}]
    with pytest.raises(DatasetConnectionError):
        ParquetConnector(server, broken).connection_check()


def test_get_connector_dispatches_to_parquet(tmp_path):
    server, tables = _two_table_server(tmp_path)
    assert isinstance(get_connector(server, tables), ParquetConnector)


def test_get_connector_rejects_external_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAANALYSIS_ENABLE_EXTERNAL_DATASETS", "false")
    with pytest.raises(DatasetConnectionError):
        get_connector({"name": "x", "type": "postgresql", "uri": "postgresql://h/db"}, [])


def test_parquet_build_server_generic_query_with_join(tmp_path):
    server, tables = _two_table_server(tmp_path)
    fast = ParquetConnector(server, tables).build_server()

    async def body():
        async with create_connected_server_and_client_session(fast) as s:
            listed = await s.list_tools()
            names = sorted(t.name for t in listed.tools)
            res = await s.call_tool("query", {
                "query": "SELECT c.region, SUM(o.amount) AS total FROM orders o "
                         "JOIN customers c ON o.cust = c.id GROUP BY c.region ORDER BY c.region"
            })
            return names, res.content[0].text, res.isError

    names, text, is_error = asyncio.run(body())
    fast._duckdb_conn.close()
    assert names == ["query"]   # one generic tool per server
    assert is_error is False
    assert text.strip() == "region,total\nN,12\nS,3"
