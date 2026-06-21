import os
os.environ["ANALYST_LLM_PROVIDER"] = "stub"

import json
import duckdb
import pytest
from src.db.schema import create_tables
from src.agent.graph import query_data_node, analyst_graph
from src.sessions.manager import ensure_session

@pytest.fixture
def mem_db():
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    yield conn
    conn.close()

class NonClosingConn:
    def __init__(self, inner): self._inner = inner
    def execute(self, *a, **kw): return self._inner.execute(*a, **kw)
    def close(self): pass

def make_mock_get_db(conn):
    def _get_db():
        return NonClosingConn(conn)
    return _get_db

def test_query_data_node_writes_audit_log(monkeypatch, mem_db):
    """query_data_node writes one audit_log row per SQL execution."""
    monkeypatch.setattr("src.agent.graph.get_db", make_mock_get_db(mem_db))
    ensure_session(mem_db, "test-audit-1")

    state = {
        "question": "test", "session_id": "test-audit-1",
        "datasets": [], "history": [],
        "plan": "", "sql": "SELECT 42 AS n", "intent": "table",
        "x_col": "", "y_col": "", "raw_rows": [], "columns": [], "response": {},
    }
    query_data_node(state)

    row = mem_db.execute("SELECT query_text, rows_affected FROM audit_log").fetchone()
    assert row is not None
    assert row[0] == "SELECT 42 AS n"
    assert row[1] == 1

def test_audit_log_records_duration(monkeypatch, mem_db):
    """duration_ms is a non-negative integer."""
    monkeypatch.setattr("src.agent.graph.get_db", make_mock_get_db(mem_db))
    ensure_session(mem_db, "test-audit-2")

    state = {
        "question": "test", "session_id": "test-audit-2",
        "datasets": [], "history": [],
        "plan": "", "sql": "SELECT 1 AS x", "intent": "table",
        "x_col": "", "y_col": "", "raw_rows": [], "columns": [], "response": {},
    }
    query_data_node(state)

    row = mem_db.execute("SELECT duration_ms FROM audit_log").fetchone()
    assert row[0] >= 0

def test_audit_log_records_session_id(monkeypatch, mem_db):
    """session_id is stored correctly in audit_log."""
    monkeypatch.setattr("src.agent.graph.get_db", make_mock_get_db(mem_db))
    ensure_session(mem_db, "my-session")

    state = {
        "question": "test", "session_id": "my-session",
        "datasets": [], "history": [],
        "plan": "", "sql": "SELECT 1", "intent": "table",
        "x_col": "", "y_col": "", "raw_rows": [], "columns": [], "response": {},
    }
    query_data_node(state)

    row = mem_db.execute("SELECT session_id FROM audit_log").fetchone()
    assert row[0] == "my-session"

def test_multiple_queries_create_multiple_audit_rows(monkeypatch, mem_db):
    """Each SQL execution creates a separate audit_log row."""
    monkeypatch.setattr("src.agent.graph.get_db", make_mock_get_db(mem_db))
    ensure_session(mem_db, "test-audit-3")

    for i in range(3):
        state = {
            "question": "test", "session_id": "test-audit-3",
            "datasets": [], "history": [],
            "plan": "", "sql": f"SELECT {i} AS n", "intent": "table",
            "x_col": "", "y_col": "", "raw_rows": [], "columns": [], "response": {},
        }
        query_data_node(state)

    count = mem_db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    assert count == 3
