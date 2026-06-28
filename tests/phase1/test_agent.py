"""Agent graph — compilation + real end-to-end run + clarify-first branch.

The end-to-end tests call the REAL Gemini API (AGENT_GEMINI_API_KEY in .env) and
use the real SQLite driver (isolated temp DB via conftest).
"""
import json

import pandas as pd
import pytest

from analysis import profiler
from analysis.dataset_store import get_dataset_store
from db.models import DatasetRow, RunRow, RunStepRow
from db.session import create_db_session


def test_graph_compiles():
    from graph.agent import agentic_ai

    assert agentic_ai is not None


@pytest.fixture
def sales_df():
    return pd.DataFrame(
        {
            "region": ["North", "South", "North", "South", "East", "West"] * 3,
            "month": ["Jan", "Feb", "Mar"] * 6,
            "sales": [100, 200, 300, 400, 500, 600] * 3,
        }
    )


def _seed(df: pd.DataFrame, question: str) -> tuple[str, str, dict]:
    prof = profiler.profile(df)
    with create_db_session() as session:
        ds = DatasetRow(
            name="sales.csv",
            file_path="/tmp/sales.csv",
            row_count=len(df),
            col_count=df.shape[1],
            profile_json=json.dumps(prof),
            size_bytes=1,
        )
        session.add(ds)
        session.flush()
        dataset_id = ds.id
        run = RunRow(dataset_id=dataset_id, question=question)
        session.add(run)
        session.flush()
        run_id = run.id
    get_dataset_store().put(dataset_id, df)
    return dataset_id, run_id, prof


@pytest.mark.usefixtures("_require_llm_key")
def test_end_to_end_run_completes(_isolated_db, sales_df):
    question = "What were total sales by region?"
    dataset_id, run_id, prof = _seed(sales_df, question)

    from graph.runner import stream_run

    events = list(
        stream_run(run_id=run_id, dataset_id=dataset_id, question=question, profile=prof)
    )
    kinds = [e["event"] for e in events]
    assert "run_started" in kinds
    assert kinds.count("step") >= 1  # at least one streamed step
    assert "answer" in kinds and "done" in kinds

    answer = next(e["data"] for e in events if e["event"] == "answer")
    assert answer["status"] == "completed"
    assert answer["prose"] and len(answer["prose"]) > 5
    assert answer["table"] is not None and answer["table"]["rows"]
    assert answer["chart"] is not None
    assert answer["code"] and "result" in answer["code"]
    assert answer["step_count"] >= 1
    assert answer["cost_usd"] >= 0
    assert answer["tokens"]["prompt"] > 0

    # Run + steps were persisted to the audit trail.
    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        assert run.status == "completed"
        assert run.prose and run.final_code
        assert run.cost_usd is not None
        steps = session.query(RunStepRow).filter_by(run_id=run_id).all()
        assert len(steps) >= 1
        # No raw region/sentinel rows in any persisted result_summary beyond aggregates.
        assert all(s.node in {"plan", "generate_code", "execute", "inspect", "finalize"} for s in steps)


@pytest.mark.usefixtures("_require_llm_key")
def test_ambiguous_question_clarifies(_isolated_db, sales_df):
    # A question with no clear metric/column mapping should trigger clarify-first.
    question = "How are things going?"
    dataset_id, run_id, prof = _seed(sales_df, question)

    from graph.runner import run_to_completion

    result = run_to_completion(
        run_id=run_id, dataset_id=dataset_id, question=question, profile=prof
    )
    assert result["status"] == "needs_clarification", result
    assert result.get("clarifying_question") or result.get("prose")

    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        assert run.status == "needs_clarification"
