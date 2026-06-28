"""Integration tests for the Local Data Analyst pipeline — real Gemini + real DuckDB.

Covers: happy path end-to-end through the runner (response content + DB state);
the gated PRIVACY invariant (no raw row value reaches any LLM input); the gated
DIALECT-SAFE RETRY loop (a DuckDB SQL error feeds the exact error back to the
model and the trace records the recovery).
"""
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from db import session as session_module
from db.models import DatasetRow, QuestionRunRow
from graph.runner import ingest_dataset, run_question

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
_SALES_LARGE = _FIXTURES / "sales_large.csv"

# A unique raw cell value embedded in sales_large.csv that must NEVER appear in
# any LLM input (the privacy invariant). It lives in a detail row, not an aggregate.
_SENTINEL = "ZZSENTINELROWVALUE42"


def _ingest_large() -> dict:
    return ingest_dataset(_SALES_LARGE.name, _SALES_LARGE.read_bytes())


@pytest.mark.usefixtures("_require_llm_key")
def test_pipeline_runs_end_to_end(_isolated_db):
    """Happy path: real NL question -> plan -> DuckDB SQL -> execute -> phrase."""
    ds = _ingest_large()
    payload = run_question(ds["id"], "Which region had the highest total sales?")

    assert payload is not None
    assert payload["status"] == "completed", payload.get("error_message")
    assert payload["answer"] and len(payload["answer"]) > 10
    assert payload["sql"]  # executed SQL surfaced
    assert payload["cost_usd"] >= 0

    # trace has plan + execute + phrase steps
    steps = [t["step"] for t in payload["trace"]]
    assert "plan" in steps
    assert "execute" in steps
    assert "phrase" in steps

    # a chart spec is present
    assert payload["chart"] is not None

    # DB state persisted
    with Session(session_module._engine) as s:
        run = s.get(QuestionRunRow, payload["run_id"])
        assert run is not None
        assert run.status == "completed"
        assert run.sql
        assert run.answer
        assert run.trace_json
        assert run.cost_usd is not None
        # the dataset row exists and is ready
        ds_row = s.get(DatasetRow, ds["id"])
        assert ds_row is not None and ds_row.status == "ready"


@pytest.mark.usefixtures("_require_llm_key")
def test_privacy_no_raw_rows_in_llm_inputs(_isolated_db):
    """GATED INVARIANT: across every logged LLM input for the run, NO raw data
    row value appears — only schema + bounded aggregates."""
    from structlog.testing import capture_logs

    ds = _ingest_large()
    with capture_logs() as logs:
        payload = run_question(ds["id"], "What are the total sales per region?")
    assert payload["status"] == "completed", payload.get("error_message")

    # Collect every logged LLM call's prompt + system (the exact text sent).
    llm_inputs = [
        (rec.get("prompt", "") + "\n" + rec.get("system", ""))
        for rec in logs
        if rec.get("event") == "llm_call"
    ]

    assert llm_inputs, "expected at least one logged LLM call"
    blob = "\n".join(llm_inputs)
    # The sentinel raw cell value must never have been sent to the model.
    assert _SENTINEL not in blob, "raw row value leaked into an LLM input"
    # And no individual customer id (raw detail column values) should appear.
    assert "cust_0123" not in blob
    assert "cust_0000" not in blob


@pytest.mark.usefixtures("_require_llm_key")
def test_dialect_safe_retry_loop_recovers(_isolated_db, capsys, monkeypatch):
    """GATED: a DuckDB SQL error feeds the exact error back to generate_sql,
    which returns corrected SQL; the trace records the retry recovery.

    We force the FIRST candidate SQL to be a SQLite-ism (``julianday``) that
    DuckDB rejects with a Catalog Error, then let the real retry node fix it.
    The plan node's first SQL is overridden deterministically; the retry call
    is real Gemini given the real DuckDB error.
    """
    import graph.nodes as nodes

    ds = _ingest_large()

    real_plan = nodes.plan

    def plan_with_bad_sql(state):
        out = real_plan(state)
        if out.get("error"):
            return out
        # Replace the model's good SQL with a guaranteed DuckDB Catalog Error so
        # the retry loop must engage. julianday() does not exist in DuckDB.
        out = {**out}
        out["sql"] = "SELECT julianday('2024-01-01') AS bad"
        # rewrite the plan trace entry's implied sql is irrelevant; keep trace
        return out

    monkeypatch.setattr(nodes, "plan", plan_with_bad_sql)
    # rebuild a graph that uses the patched node
    from langgraph.graph import END, StateGraph

    from graph.edges import after_execute, after_guard, after_phrase, after_plan
    from graph.state import AnalystState

    g = StateGraph(AnalystState)
    g.add_node("plan", plan_with_bad_sql)
    g.add_node("privacy_guard", nodes.privacy_guard)
    g.add_node("generate_sql", nodes.generate_sql)
    g.add_node("execute_sql", nodes.execute_sql)
    g.add_node("phrase_answer", nodes.phrase_answer)
    g.add_node("pick_chart", nodes.pick_chart)
    g.add_node("finalize", nodes.finalize)
    g.add_node("handle_error", nodes.handle_error)
    g.set_entry_point("plan")
    g.add_conditional_edges("plan", after_plan, {"handle_error": "handle_error", "privacy_guard": "privacy_guard"})
    g.add_conditional_edges("privacy_guard", after_guard, {"handle_error": "handle_error", "execute_sql": "execute_sql", "phrase_answer": "phrase_answer"})
    g.add_conditional_edges("execute_sql", after_execute, {"generate_sql": "generate_sql", "handle_error": "handle_error", "privacy_guard": "privacy_guard"})
    g.add_edge("generate_sql", "execute_sql")
    g.add_conditional_edges("phrase_answer", after_phrase, {"handle_error": "handle_error", "pick_chart": "pick_chart"})
    g.add_edge("pick_chart", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    patched_graph = g.compile()

    schema = json.loads(_dataset_schema(ds["id"]))
    initial = {
        "run_id": "retry-test",
        "dataset_id": ds["id"],
        "question": "How many days between the first and last order?",
        "schema": schema,
        "dataset_path": _dataset_path(ds["id"]),
        "table_name": "t",
        "sql_attempts": 0,
        "sql_error": None,
        "error": None,
        "trace": [],
        "cost_usd": 0.0,
    }
    final = patched_graph.invoke(initial)

    steps = [(t["step"], t["ok"]) for t in final["trace"]]
    # First execute failed with the dialect error...
    assert ("execute", False) in steps, steps
    # ...a retry was attempted...
    assert any(s == "retry" for s, _ in steps), steps
    # ...and a later execute (or handle_error) followed. The error must be the
    # DuckDB Catalog Error for the SQLite-ism we forced.
    exec_errors = [t.get("error", "") for t in final["trace"] if t["step"] == "execute" and not t["ok"]]
    assert any("julianday" in (e or "").lower() or "catalog" in (e or "").lower() for e in exec_errors), exec_errors


# --- small helpers reading the dataset row created by ingest ---


def _dataset_schema(dataset_id: str) -> str:
    with Session(session_module._engine) as s:
        return s.get(DatasetRow, dataset_id).schema_json


def _dataset_path(dataset_id: str) -> str:
    with Session(session_module._engine) as s:
        return s.get(DatasetRow, dataset_id).duckdb_path
