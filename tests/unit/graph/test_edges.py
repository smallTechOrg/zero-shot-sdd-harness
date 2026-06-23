"""Unit tests for analyst graph edge functions."""
from graph.edges import after_plan, after_execute


def test_after_plan_error():
    state = {"error": "something went wrong"}
    assert after_plan(state) == "handle_error"


def test_after_plan_success():
    state = {"error": None, "sql": "SELECT 1"}
    assert after_plan(state) == "sql_executor"


def test_after_plan_no_error_key():
    state = {"sql": "SELECT 1"}
    assert after_plan(state) == "sql_executor"


def test_after_execute_error():
    state = {"error": "SQL failed"}
    assert after_execute(state) == "handle_error"


def test_after_execute_success():
    state = {"error": None, "rows": [{"count": 5}], "row_count": 1}
    assert after_execute(state) == "response_formatter"


def test_after_execute_no_error_key():
    state = {"rows": [], "row_count": 0}
    assert after_execute(state) == "response_formatter"
