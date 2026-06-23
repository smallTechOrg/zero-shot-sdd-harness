"""
Integration tests for the analyst graph against real Gemini API.

These tests run the real LLM (Gemini) with actual SQLite tables.
Requires AGENT_GEMINI_API_KEY in .env.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import db.session as session_module
from db.models import Base
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _isolated_db_graph(tmp_path, monkeypatch):
    """Use an isolated SQLite DB for each test."""
    db_path = tmp_path / "test_graph.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("AGENT_DATABASE_URL", db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)

    import llm.providers.gemini as gmod
    gmod._provider = None

    yield engine

    engine.dispose()
    session_module._engine = None
    session_module._SessionLocal = None
    gmod._provider = None


@pytest.fixture(autouse=True)
def _require_gemini():
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("AGENT_GEMINI_API_KEY not set — required for integration tests")


def _seed_table(session_id: str, filename: str, csv_data: str) -> str:
    """Load CSV data into SQLite via the ingest pipeline. Returns table_name."""
    import io
    import pandas as pd
    from ingest.loader import load_dataset

    df = pd.read_csv(io.StringIO(csv_data))
    data = load_dataset(session_id, filename, df)
    return data["table_name"]


def test_query_planner_generates_select():
    """query_planner generates a SELECT statement via real Gemini."""
    session_id = "graph-test-11111111-1111-1111-1111-111111111111"
    table_name = _seed_table(
        session_id,
        "revenue.csv",
        "region,revenue\nNorth,500\nSouth,300\nEast,700\n",
    )

    from graph.nodes import query_planner
    state = {
        "session_id": session_id,
        "dataset_table": table_name,
        "question": "What is the total revenue?",
    }
    result = query_planner(state)

    assert result.get("error") is None, f"query_planner error: {result.get('error')}"
    assert result["sql"].strip().upper().startswith("SELECT")
    assert result.get("sql_explanation")


def test_full_graph_run_end_to_end():
    """Full graph: seed table → invoke analyst_graph → assert answer + audit."""
    session_id = "full-graph-11111111-1111-1111-1111-111111111111"
    table_name = _seed_table(
        session_id,
        "sales.csv",
        "product,sales\nWidget A,100\nWidget B,200\nWidget C,150\n",
    )

    from graph.agent import analyst_graph
    from db.session import create_db_session
    from db.models import AuditLogRow
    from sqlalchemy import select

    initial = {
        "session_id": session_id,
        "dataset_table": table_name,
        "question": "What is the total sales amount?",
    }
    final = analyst_graph.invoke(initial)

    assert final.get("error") is None, f"Graph error: {final.get('error')}"
    assert final.get("answer")
    assert final.get("sql", "").strip().upper().startswith("SELECT")
    assert final.get("audit_id")

    # Audit row written — check inside the session context to avoid DetachedInstanceError
    with create_db_session() as sess:
        rows = sess.scalars(
            select(AuditLogRow).where(AuditLogRow.session_id == session_id)
        ).all()
        assert len(rows) >= 1
        assert rows[-1].sql_generated is not None


def test_graph_error_on_nonexistent_table():
    """Graph sets error when dataset_table doesn't exist in SQLite."""
    session_id = "err-test-11111111-1111-1111-1111-111111111111"

    from graph.agent import analyst_graph
    initial = {
        "session_id": session_id,
        "dataset_table": "err_test_11111111_1111_1111_1111_111111111111_nonexistent",
        "question": "How many rows?",
    }
    final = analyst_graph.invoke(initial)
    # Either query_planner or sql_executor should set error
    assert final.get("error") is not None
