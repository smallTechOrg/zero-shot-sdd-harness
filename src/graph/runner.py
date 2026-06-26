"""Runner for the pandas Q&A analysis pipeline."""
import json
import time

from graph.agent import agentic_ai
from graph.state import AgentState
from db.session import create_db_session
from db.models import AnalysisRun
from sessions.store import get as get_session_df
from observability.events import get_logger

_log = get_logger("runner")


def run_analysis(session_id: str, question: str) -> str:
    """Invoke the graph for a given session + question. Returns run_id."""
    df = get_session_df(session_id)
    if df is None:
        raise ValueError(f"Session {session_id} not found in memory store.")

    t0 = time.monotonic()

    # Create pending run
    with create_db_session() as db:
        run = AnalysisRun(session_id=session_id, question=question, status="pending")
        db.add(run)
        db.flush()
        run_id = run.id

    # Invoke graph
    initial: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "question": question,
        "dataframe": df,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "node_trace": [],
        "error": None,
    }
    final = agentic_ai.invoke(initial)

    latency_ms = round((time.monotonic() - t0) * 1000, 2)

    # Persist results
    with create_db_session() as db:
        row = db.get(AnalysisRun, run_id)
        if row:
            row.answer = final.get("answer")
            row.status = final.get("status", "completed")
            row.error_message = final.get("error")
            row.tokens_in = final.get("tokens_in")
            row.tokens_out = final.get("tokens_out")
            row.cost_usd = final.get("cost_usd")
            row.latency_ms = latency_ms
            row.model = final.get("model")
            nt = final.get("node_trace")
            row.node_trace = json.dumps(nt) if nt else None
            row.chart_data = None
            row.executed_code = None

    _log.info("run.complete", run_id=run_id, status=final.get("status"), latency_ms=latency_ms)
    return run_id
