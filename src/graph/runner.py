"""Run a single analysis through the ReAct graph.

Phase 2 signature (single-dataset Q&A, no sessions yet). Pre-flight selector /
clarification and follow-up suggestions are Phase 3 — hooks are left but not
implemented here. The runner creates the `query_runs` row, invokes the compiled
`agentic_ai` graph, persists the result, and returns the payload `/ask` needs.
"""
from __future__ import annotations

from typing import Any

from config.settings import get_settings
from db.models import QueryRunRow
from db.session import create_db_session
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

logger = get_logger("graph.runner")


def run_agent(
    question: str,
    dataset_ids: list[str],
    *,
    session_id: str | None = None,
    conversation_history: list[dict] | None = None,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """Run the ReAct loop for `question` over `dataset_ids`; return the `/ask` payload.

    Returns a dict with the keys slice-2c's `/ask` route consumes:
        run_id, status, answer, iteration_count, tokens_input, tokens_output,
        action_history, charts, dataset_ids, is_best_effort, selector_reasoning.
    """
    settings = get_settings()
    cap = max_iterations if max_iterations is not None else settings.max_iterations

    # 1. Create the query_runs row (status=running).
    with create_db_session() as session:
        row = QueryRunRow(
            dataset_id=dataset_ids[0] if dataset_ids else None,
            session_id=session_id,
            question=question,
            status="running",
            dataset_ids_json=list(dataset_ids),
            iteration_count=0,
            tokens_input=0,
            tokens_output=0,
        )
        session.add(row)
        session.flush()
        run_id = row.id

    logger.info("run_start", run_id=run_id, datasets=len(dataset_ids), max_iterations=cap)

    # 2. Build the initial AgentState and invoke the graph.
    initial: AgentState = {
        "run_id": run_id,
        "dataset_ids": list(dataset_ids),
        "session_id": session_id,
        "question": question,
        "conversation_history": conversation_history or [],
        "action_history": [],
        "iteration_count": 0,
        "tokens_input": 0,
        "tokens_output": 0,
        "charts": [],
        "status": "running",
        "max_iterations": cap,
        "error": None,
    }

    # The graph self-terminates via force_finalize at iteration >= cap; give the
    # recursion limit generous headroom (3 nodes per loop + setup/finalize).
    config = {"recursion_limit": cap * 3 + 10}
    final: dict[str, Any] = agentic_ai.invoke(initial, config=config)

    status = final.get("status", "completed")
    answer = final.get("answer")
    action_history = final.get("action_history") or []
    iteration_count = final.get("iteration_count", 0)
    tokens_input = final.get("tokens_input", 0)
    tokens_output = final.get("tokens_output", 0)
    error_message = final.get("error_message") or final.get("error")
    selector_reasoning = final.get("selector_reasoning")
    charts = final.get("charts") or []
    # is_best_effort == force-finalized (informational error_message set, run completed).
    is_best_effort = status == "completed" and error_message in ("max_iterations", "consecutive_errors")

    # 3. Persist the result to the query_runs row.
    with create_db_session() as session:
        row = session.get(QueryRunRow, run_id)
        if row is not None:
            row.status = status
            row.answer = answer
            row.action_history = action_history
            row.iteration_count = iteration_count
            row.tokens_input = tokens_input
            row.tokens_output = tokens_output
            row.error_message = error_message
            row.selector_reasoning = selector_reasoning

    logger.info(
        "run_done",
        run_id=run_id,
        status=status,
        iterations=iteration_count,
        is_best_effort=is_best_effort,
    )

    # 4. Return the payload slice-2c's /ask route consumes.
    return {
        "run_id": run_id,
        "status": status,
        "answer": answer,
        "iteration_count": iteration_count,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "action_history": action_history,
        "charts": charts,
        "dataset_ids": list(dataset_ids),
        "is_best_effort": is_best_effort,
        "selector_reasoning": selector_reasoning,
    }
