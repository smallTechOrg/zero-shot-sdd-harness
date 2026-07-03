"""Synchronous run entry point for the data-analysis agent.

``run_analysis`` creates the ``running`` RunRow, threads any prior conversation
turns for the session into the graph state, streams the graph so per-node
progress events reach the SSE bus, rolls up token/cost usage, and returns the
run_id. The graph's ``finalize``/``handle_error`` nodes persist the rest of the
run — the caller re-loads the RunRow to build the API response.
"""
from __future__ import annotations

from uuid import uuid4

from graph.agent import agentic_ai
from graph.state import AgentState
from db.session import create_db_session, init_db
from db.models import RunRow
from llm.client import reset_usage, get_usage, estimate_cost_usd
from observability.progress import progress_bus
from observability.events import get_logger

_log = get_logger("runner")

# Cap conversation memory threaded into the prompt so a long session cannot
# grow the prompt without bound (privacy + cost).
MAX_HISTORY_TURNS = 6


def _load_session_messages(session_id: str) -> list[dict]:
    """Load prior COMPLETED turns for a session as conversation memory.

    Returns ``[{"question", "answer"}]`` oldest→newest, capped to the last
    ``MAX_HISTORY_TURNS`` turns. Only prior questions + aggregated answer text —
    never raw rows.
    """
    with create_db_session() as session:
        rows = (
            session.query(RunRow)
            .filter(RunRow.session_id == session_id, RunRow.status == "completed")
            .order_by(RunRow.created_at.asc())
            .all()
        )
        messages = [
            {"question": r.question, "answer": r.answer_text or ""} for r in rows
        ]
    return messages[-MAX_HISTORY_TURNS:]


def _publish_progress(run_id: str, node_name: str, partial: dict | None) -> None:
    """Map a graph node entering into a user-facing live-progress step."""
    partial = partial or {}
    if node_name == "load_context":
        progress_bus.publish(run_id, "Planning…", "Loading dataset")
    elif node_name == "generate_code":
        attempts = partial.get("attempts", 1) or 1
        if attempts > 1:
            progress_bus.publish(run_id, "Retrying…", "Writing analysis code")
        else:
            progress_bus.publish(run_id, "Planning…", "Writing analysis code")
    elif node_name == "execute_code":
        progress_bus.publish(run_id, "Running code…", "")
    elif node_name == "write_answer":
        progress_bus.publish(run_id, "Writing answer…", "")
    # finalize / handle_error are terminal — the stream's finally-block finishes.


def run_analysis(
    dataset_id: str,
    question: str,
    *,
    session_id: str | None = None,
    run_id: str | None = None,
    messages: list[dict] | None = None,
) -> str:
    """Run one analysis synchronously; returns the run_id.

    ``run_id`` may be supplied by the client so an SSE progress subscriber can
    correlate before the run starts; otherwise a fresh uuid is used.
    """
    init_db()

    resolved_run_id = run_id or str(uuid4())

    # Conversation memory: explicit messages win; else load the session's turns.
    if messages is None and session_id:
        messages = _load_session_messages(session_id)
    if messages is None:
        messages = []

    with create_db_session() as session:
        run = RunRow(
            id=resolved_run_id,
            dataset_id=dataset_id,
            question=question,
            session_id=session_id,
            status="running",
        )
        session.add(run)
        session.flush()

    # Start fresh token accumulation for THIS run (contextvar-scoped). The graph
    # runs its sync nodes in this same thread, so the accumulator propagates.
    reset_usage()

    initial: AgentState = {
        "run_id": resolved_run_id,
        "dataset_id": dataset_id,
        "question": question,
        "messages": messages,
        "error": None,
    }

    final_status = "completed"
    try:
        for update in agentic_ai.stream(initial, stream_mode="updates"):
            for node_name, partial in update.items():
                _publish_progress(resolved_run_id, node_name, partial)

        # Roll up token/cost usage onto the run row (degrade to none if 0).
        usage = get_usage()
        total_tokens = usage.get("total_tokens", 0) or 0
        if total_tokens > 0:
            cost = estimate_cost_usd(
                usage.get("input_tokens", 0) or 0,
                usage.get("output_tokens", 0) or 0,
            )
            with create_db_session() as session:
                run = session.get(RunRow, resolved_run_id)
                if run is not None:
                    run.tokens_used = total_tokens
                    run.cost_estimate_usd = cost

        with create_db_session() as session:
            run = session.get(RunRow, resolved_run_id)
            final_status = run.status if run and run.status else "completed"
    except Exception as exc:  # noqa: BLE001
        _log.error("run_analysis.error", run_id=resolved_run_id, error=str(exc))
        final_status = "failed"
        raise
    finally:
        # ALWAYS finish so the SSE stream never hangs.
        progress_bus.finish(resolved_run_id, final_status)

    return resolved_run_id
