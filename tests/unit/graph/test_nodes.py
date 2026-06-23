"""Unit tests for analyst graph nodes (no LLM calls — use mocks)."""


# ---------------------------------------------------------------------------
# response_formatter (pure logic — no DB, no LLM)
# ---------------------------------------------------------------------------

def test_response_formatter_empty_rows():
    from graph.nodes import response_formatter
    state = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "How many rows?",
        "sql_explanation": "Count of all rows",
        "rows": [],
        "row_count": 0,
        "sql": "SELECT COUNT(*) FROM test",
    }
    result = response_formatter(state)
    assert "No results" in result["answer"]
    assert result["table"] == []


def test_response_formatter_null_values():
    from graph.nodes import response_formatter
    state = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "Show data",
        "sql_explanation": "All data",
        "rows": [{"name": None, "value": 42}],
        "row_count": 1,
        "sql": "SELECT * FROM test",
    }
    result = response_formatter(state)
    assert "—" in result["answer"]
    assert result["table"] == [{"name": None, "value": 42}]


def test_response_formatter_row_cap_message():
    from graph.nodes import response_formatter
    rows = [{"col": i} for i in range(5)]
    state = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "All data",
        "sql_explanation": "All rows",
        "rows": rows,
        "row_count": 100,
        "sql": "SELECT * FROM test",
    }
    result = response_formatter(state)
    assert "5 of 100" in result["answer"]


# ---------------------------------------------------------------------------
# handle_error (no DB side-effects when DB not available — just logs)
# ---------------------------------------------------------------------------

def test_handle_error_returns_state(_isolated_db):
    from graph.nodes import handle_error
    state = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "What?",
        "error": "Something went wrong",
    }
    result = handle_error(state)
    # handle_error returns the original state (possibly with audit id attempt)
    assert result.get("error") == "Something went wrong"


# ---------------------------------------------------------------------------
# finalize (no-op)
# ---------------------------------------------------------------------------

def test_finalize_passthrough():
    from graph.nodes import finalize
    state = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "?",
        "answer": "42",
        "audit_id": "audit-1",
    }
    result = finalize(state)
    assert result == state


# ---------------------------------------------------------------------------
# audit_logger
# ---------------------------------------------------------------------------

def test_audit_logger_writes_to_db(_isolated_db):
    from db.session import create_db_session
    from db.models import AuditLogRow, SessionRow
    from graph.nodes import audit_logger
    from sqlalchemy import select

    # Seed session
    with create_db_session() as sess:
        sess.add(SessionRow(id="s1"))

    state = {
        "session_id": "s1",
        "dataset_table": "s1_test",
        "question": "How many?",
        "sql": "SELECT COUNT(*) FROM s1_test",
        "sql_explanation": "Row count",
        "rows": [{"count": 5}],
        "row_count": 5,
        "duration_ms": 20,
        "answer": "5 rows",
    }
    result = audit_logger(state)
    assert result.get("audit_id")

    with create_db_session() as sess:
        rows = sess.scalars(select(AuditLogRow)).all()
        assert len(rows) == 1
        assert rows[0].question == "How many?"
        assert rows[0].sql_generated == "SELECT COUNT(*) FROM s1_test"
        assert rows[0].row_count == 5
        assert rows[0].duration_ms == 20
        assert rows[0].error is None
