"""Smoke tests — no LLM key required."""


def test_import_models():
    from db.models import SessionRow, DatasetRow, AuditLogRow
    assert SessionRow.__tablename__ == "sessions"
    assert DatasetRow.__tablename__ == "datasets"
    assert AuditLogRow.__tablename__ == "audit_log"


def test_import_state():
    from graph.state import AnalystState
    # TypedDict — just check it's importable
    assert AnalystState is not None


def test_graph_compiles():
    """Graph compiles without requiring real API keys (lazy provider init)."""
    from graph.agent import analyst_graph
    assert analyst_graph is not None
