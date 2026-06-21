import os

os.environ["ANALYST_LLM_PROVIDER"] = "stub"

import json

import duckdb
import pytest

from src.agent.graph import analyst_graph, plan_node, respond_node
from src.db.schema import create_tables


@pytest.fixture
def mem_db_with_sales():
    """In-memory DuckDB with a sales view pre-loaded."""
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    conn.execute("""
        CREATE VIEW sales AS
        SELECT * FROM (VALUES
            ('widget', 100),
            ('gadget', 200),
            ('thingamajig', 150)
        ) t(product, revenue)
    """)
    yield conn
    conn.close()


def make_mock_get_db(conn):
    """Returns a factory that yields a non-closing proxy to the shared fixture connection."""
    class NonClosingConn:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, *a, **kw):
            return self._inner.execute(*a, **kw)

        def close(self):
            pass  # don't close the shared fixture connection

    def _get_db():
        return NonClosingConn(conn)

    return _get_db


def test_plan_node_returns_table_intent():
    """plan_node with stub LLM returns intent=table and a SQL string."""
    state = {
        "question": "show top 10 rows of sales",
        "session_id": "test",
        "datasets": ["sales"],
        "plan": "",
        "sql": "",
        "intent": "table",
        "raw_rows": [],
        "columns": [],
        "response": {},
    }
    result = plan_node(state)
    assert result["intent"] == "table"
    assert "SELECT" in result["sql"].upper()


def test_full_table_query_returns_markdown(monkeypatch, mem_db_with_sales):
    """Full graph: stub LLM + in-memory DuckDB → Markdown table response."""
    monkeypatch.setattr("src.agent.graph.get_db", make_mock_get_db(mem_db_with_sales))

    from src.integrations import llm as llm_mod

    class ControlledStub:
        def complete(self, prompt, system=""):
            return json.dumps({"intent": "table", "sql": "SELECT * FROM sales LIMIT 10"})

    monkeypatch.setattr(llm_mod, "StubLLMClient", ControlledStub)
    monkeypatch.setattr(llm_mod, "get_llm_client", lambda: ControlledStub())

    result = analyst_graph.invoke({
        "question": "show top 10 rows of sales",
        "session_id": "test",
        "datasets": ["sales"],
        "plan": "",
        "sql": "",
        "intent": "table",
        "raw_rows": [],
        "columns": [],
        "response": {},
    })

    response = result["response"]
    assert response["type"] == "table"
    assert "markdown" in response
    assert "product" in response["markdown"]
    assert "revenue" in response["markdown"]
    assert "widget" in response["markdown"]


def test_markdown_table_has_header_and_separator(monkeypatch, mem_db_with_sales):
    """Markdown table includes GFM header row and separator."""
    monkeypatch.setattr("src.agent.graph.get_db", make_mock_get_db(mem_db_with_sales))

    from src.integrations import llm as llm_mod

    class ControlledStub:
        def complete(self, prompt, system=""):
            return json.dumps({"intent": "table", "sql": "SELECT * FROM sales LIMIT 10"})

    monkeypatch.setattr(llm_mod, "get_llm_client", lambda: ControlledStub())

    result = analyst_graph.invoke({
        "question": "show rows",
        "session_id": "test",
        "datasets": ["sales"],
        "plan": "",
        "sql": "",
        "intent": "table",
        "raw_rows": [],
        "columns": [],
        "response": {},
    })

    md = result["response"]["markdown"]
    lines = md.strip().split("\n")
    assert lines[0].startswith("|")   # header row
    assert "---" in lines[1]          # separator row
    assert len(lines) >= 4            # header + sep + at least 2 data rows


def test_respond_node_handles_empty_result():
    """respond_node with empty rows returns a valid Markdown table with no data rows."""
    state = {
        "question": "show rows",
        "session_id": "test",
        "datasets": [],
        "plan": "",
        "sql": "",
        "intent": "table",
        "raw_rows": [],
        "columns": ["product", "revenue"],
        "response": {},
    }
    result = respond_node(state)
    assert result["response"]["type"] == "table"
    assert "product" in result["response"]["markdown"]
    assert "---" in result["response"]["markdown"]
