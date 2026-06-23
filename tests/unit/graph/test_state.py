"""Unit tests for AnalystState TypedDict."""


def test_analyst_state_is_total_false():
    """AnalystState should be constructible with partial keys."""
    from graph.state import AnalystState

    state: AnalystState = {
        "session_id": "abc",
        "question": "How many rows?",
    }
    assert state["session_id"] == "abc"
    assert state["question"] == "How many rows?"
    # Optional keys absent — no error
    assert state.get("sql") is None
    assert state.get("error") is None


def test_analyst_state_full():
    """AnalystState can hold all defined keys."""
    from graph.state import AnalystState

    state: AnalystState = {
        "session_id": "s1",
        "dataset_table": "s1_sales",
        "question": "What is the total revenue?",
        "schema_context": "Table: s1_sales\nColumns: revenue (REAL)",
        "sql": "SELECT SUM(revenue) FROM s1_sales",
        "sql_explanation": "Sum of all revenue values",
        "rows": [{"sum(revenue)": 1000}],
        "row_count": 1,
        "duration_ms": 12,
        "answer": "Total revenue is $1000.",
        "table": [{"sum(revenue)": 1000}],
        "audit_id": "audit-123",
        "error": None,
    }
    assert state["dataset_table"] == "s1_sales"
    assert state["sql"] == "SELECT SUM(revenue) FROM s1_sales"
    assert state["audit_id"] == "audit-123"
