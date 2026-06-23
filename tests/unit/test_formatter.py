"""Response formatter unit tests — no LLM key required."""
from graph.state import AnalystState
import graph.nodes as nodes


def test_format_empty_rows():
    state: AnalystState = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "How many rows?",
        "sql_explanation": "Count of all rows",
        "rows": [],
        "row_count": 0,
        "sql": "SELECT COUNT(*) FROM test",
    }
    result = nodes.response_formatter(state)
    assert "No results" in result["answer"]


def test_format_null_values():
    state: AnalystState = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "Show data",
        "sql_explanation": "All data",
        "rows": [{"name": None, "value": 42}],
        "row_count": 1,
        "sql": "SELECT * FROM test",
    }
    result = nodes.response_formatter(state)
    assert "—" in result["answer"]


def test_format_shows_row_cap_message():
    """When row_count > len(rows), formatter shows 'Showing X of Y rows'."""
    rows = [{"col": i} for i in range(5)]
    state: AnalystState = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "All data",
        "sql_explanation": "All rows",
        "rows": rows,
        "row_count": 100,
        "sql": "SELECT * FROM test",
    }
    result = nodes.response_formatter(state)
    assert "5 of 100" in result["answer"]


def test_format_single_row():
    state: AnalystState = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "Count",
        "sql_explanation": "Row count",
        "rows": [{"count": 42}],
        "row_count": 1,
        "sql": "SELECT COUNT(*) as count FROM test",
    }
    result = nodes.response_formatter(state)
    assert "42" in result["answer"]
    assert result["table"] == [{"count": 42}]


def test_format_truncates_long_values():
    """Cell values longer than 50 chars should be truncated."""
    long_val = "x" * 100
    state: AnalystState = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "Show",
        "sql_explanation": "All data",
        "rows": [{"text": long_val}],
        "row_count": 1,
        "sql": "SELECT * FROM test",
    }
    result = nodes.response_formatter(state)
    # The long value should be truncated to 50 chars in the table
    assert long_val not in result["answer"]
    assert "x" * 50 in result["answer"]
