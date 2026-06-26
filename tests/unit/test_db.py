"""DB layer tests — no LLM key required."""
import json
from sqlalchemy.orm import Session
from db.models import SessionRow, AnalysisRun


def test_session_row_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        row = SessionRow(
            original_filename="test.csv",
            row_count=10,
            column_schema=json.dumps([{"name": "id", "dtype": "int64"}]),
        )
        s.add(row)
        s.commit()
        session_id = row.id

    with Session(_isolated_db) as s:
        fetched = s.get(SessionRow, session_id)
        assert fetched is not None
        assert fetched.original_filename == "test.csv"
        assert fetched.row_count == 10
        schema = json.loads(fetched.column_schema)
        assert schema[0]["name"] == "id"


def test_analysis_run_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        session_row = SessionRow(
            original_filename="sales.csv",
            row_count=5,
            column_schema="[]",
        )
        s.add(session_row)
        s.commit()
        session_id = session_row.id

    with Session(_isolated_db) as s:
        run = AnalysisRun(
            session_id=session_id,
            question="What are total sales?",
            status="pending",
        )
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(AnalysisRun, run_id)
        assert run is not None
        assert run.question == "What are total sales?"
        assert run.status == "pending"
        assert run.answer is None


def test_analysis_run_status_update(_isolated_db):
    with Session(_isolated_db) as s:
        session_row = SessionRow(
            original_filename="data.csv",
            row_count=3,
            column_schema="[]",
        )
        s.add(session_row)
        s.commit()
        session_id = session_row.id

    with Session(_isolated_db) as s:
        run = AnalysisRun(
            session_id=session_id,
            question="Test?",
            status="pending",
        )
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(AnalysisRun, run_id)
        run.status = "completed"
        run.answer = "The answer is 42."
        run.tokens_in = 100
        run.tokens_out = 50
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(AnalysisRun, run_id)
        assert run.status == "completed"
        assert run.answer == "The answer is 42."
        assert run.tokens_in == 100
        assert run.tokens_out == 50
