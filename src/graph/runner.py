"""Entry point that drives a single analyst run end-to-end."""
from __future__ import annotations

import json
import time

from analyst.profile import profile_csv
from db.models import DatasetRow, RunRow
from db.session import create_db_session
from graph.agent import agentic_ai
from graph import events_bus
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("runner")

DEFAULT_MAX_RETRIES = 3


def create_run_row(dataset_id: str, question: str) -> str:
    """Insert a `running` run row and return its id."""
    with create_db_session() as session:
        run = RunRow(dataset_id=dataset_id, question=question, status="running",
                     steps_json="[]", tokens=0)
        session.add(run)
        session.flush()
        return run.id


def run_agent(
    dataset_id: str,
    question: str,
    *,
    run_id: str | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    """Drive the LangGraph run, persist the audit trail, publish stream events.

    Reuses an existing `run_id` (e.g. created by the API before dispatch) or
    creates one. Returns the run_id.
    """
    if run_id is None:
        run_id = create_run_row(dataset_id, question)

    started = time.monotonic()

    # Load dataset metadata (schema + sample for the LLM; path for the sandbox).
    with create_db_session() as session:
        ds = session.get(DatasetRow, dataset_id)
        if ds is None:
            _fail(run_id, f"Dataset {dataset_id} not found")
            return run_id
        csv_path = ds.path
        schema = json.loads(ds.schema_json)
        sample = json.loads(ds.sample_json)

    initial: AgentState = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "csv_paths": {"df": csv_path},
        "question": question,
        "schema": schema,
        "sample_rows": sample,
        "attempts": [],
        "retries": 0,
        "max_retries": max_retries,
        "tokens": 0,
        "error": None,
    }

    try:
        final = agentic_ai.invoke(
            initial, config={"recursion_limit": 50}
        )
    except Exception as exc:  # graph-level crash — never crash the dispatcher
        _log.error("run_crash", run_id=run_id, error=str(exc))
        _fail(run_id, f"Run crashed: {exc}")
        return run_id

    status = final.get("status", "failed")
    attempts = final.get("attempts", [])
    tokens = final.get("tokens", 0)
    elapsed = int((time.monotonic() - started) * 1000)
    _log.info("run_done", run_id=run_id, status=status, duration_ms=elapsed,
              tokens=tokens, attempts=len(attempts))

    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        if run is not None:
            run.status = status
            run.plan = final.get("plan")
            run.steps_json = json.dumps(attempts)
            run.answer = final.get("answer")
            run.chart_spec_json = (
                json.dumps(final["chart_spec"]) if final.get("chart_spec") else None
            )
            run.table_json = (
                json.dumps(final["table"]) if final.get("table") else None
            )
            run.tokens = tokens
            run.error_message = final.get("error") if status == "failed" else None

    if status == "completed":
        events_bus.publish(run_id, "final", {
            "status": "completed",
            "answer": final.get("answer"),
            "chart_spec": final.get("chart_spec"),
            "table": final.get("table"),
            "code": final.get("code"),
        })
    else:
        events_bus.publish(run_id, "error", {
            "status": "failed",
            "error": final.get("error") or "Run failed.",
        })
    events_bus.close_stream(run_id)
    return run_id


def _fail(run_id: str, message: str) -> None:
    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        if run is not None:
            run.status = "failed"
            run.error_message = message
    events_bus.publish(run_id, "error", {"status": "failed", "error": message})
    events_bus.close_stream(run_id)
