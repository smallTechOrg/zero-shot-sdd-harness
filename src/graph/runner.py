"""Streaming runner — drives the agent graph, yields SSE step events, and
persists the run + per-step audit rows.

It imports the DB models BY NAME at runtime (the db-schema slice owns
``src/db/models.py``). The runner is a generator yielding SSE-shaped dicts:

    {"event": "run_started", "data": {...}}
    {"event": "step",        "data": {...}}   # one per node executed
    {"event": "answer",      "data": {...}}   # final answer (completed/clarify)
    {"event": "done",        "data": {...}}
    {"event": "error",       "data": {...}}   # on failure

Token/cost are accumulated into the state by the nodes and persisted to the
``runs`` row; the daily total is derivable by summing ``runs.cost_usd`` for a day.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Iterator

from config.settings import get_settings
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("agent.runner")

# Human-readable order labels for the SSE step counter ("Step N of M").
_NODE_LABELS = {
    "plan": "Planning",
    "generate_code": "Writing code",
    "execute": "Running code",
    "inspect": "Inspecting result",
    "finalize": "Composing answer",
    "clarify": "Asking for clarification",
    "handle_error": "Handling error",
}

# Maps a node to the RunStep "node" value the data model expects.
_AUDIT_NODES = {"plan", "generate_code", "execute", "inspect", "finalize", "clarify"}


def stream_run(
    *,
    run_id: str,
    dataset_id: str,
    question: str,
    profile: dict,
    messages: list | None = None,
    max_steps: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Execute one run, yielding SSE-shaped step events and persisting steps.

    The dataset's DataFrame must already be loaded into the ``DatasetStore``
    (done at upload). Raw rows are never passed in state — ``node_execute``
    reads the frame from the store.
    """
    settings = get_settings()
    initial: AgentState = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "question": question,
        "messages": messages or [],
        "profile": profile,
        "step_index": 0,
        "max_steps": int(max_steps if max_steps is not None else settings.max_steps),
        "tokens": {"prompt": 0, "completion": 0},
        "cost_usd": 0.0,
        "error": None,
    }

    yield _sse("run_started", {"run_id": run_id, "dataset_id": dataset_id, "max_steps": initial["max_steps"]})

    final_state: dict[str, Any] = dict(initial)
    step_order = 0
    last_node_start = time.perf_counter()

    try:
        for chunk in agentic_ai.stream(initial, stream_mode="updates"):
            for node_name, delta in chunk.items():
                now = time.perf_counter()
                latency_ms = int((now - last_node_start) * 1000)
                last_node_start = now
                if isinstance(delta, dict):
                    final_state.update(delta)

                if node_name in _AUDIT_NODES:
                    step_order += 1
                    step_payload = _step_payload(node_name, final_state, step_order, latency_ms)
                    _persist_step(run_id, step_order, node_name, final_state, latency_ms)
                    yield _sse("step", step_payload)

        status = final_state.get("status") or ("failed" if final_state.get("error") else "completed")

        if status == "failed" or final_state.get("error"):
            _persist_run(run_id, final_state, status="failed")
            yield _sse("error", {"run_id": run_id, "error": final_state.get("error")})
            yield _sse("done", {"run_id": run_id, "status": "failed"})
            return

        _persist_run(run_id, final_state, status=status)
        yield _sse(
            "answer",
            {
                "run_id": run_id,
                "status": status,
                "prose": final_state.get("prose"),
                "chart": final_state.get("chart"),
                "table": final_state.get("table"),
                "code": final_state.get("code"),
                "follow_ups": final_state.get("follow_ups", []),
                "clarifying_question": final_state.get("clarifying_question"),
                "tokens": final_state.get("tokens"),
                "cost_usd": final_state.get("cost_usd"),
                "step_count": step_order,
            },
        )
        yield _sse("done", {"run_id": run_id, "status": status})
    except Exception as exc:  # infra failure outside node try/except
        _log.error("runner_failed", run_id=run_id, error=str(exc))
        final_state["error"] = str(exc)
        _persist_run(run_id, final_state, status="failed")
        yield _sse("error", {"run_id": run_id, "error": str(exc)})
        yield _sse("done", {"run_id": run_id, "status": "failed"})


def run_to_completion(
    *,
    run_id: str,
    dataset_id: str,
    question: str,
    profile: dict,
    messages: list | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    """Drive ``stream_run`` to completion and return the final answer event.

    Convenience for tests and non-streaming callers.
    """
    last_answer: dict[str, Any] | None = None
    last_error: dict[str, Any] | None = None
    steps = 0
    for event in stream_run(
        run_id=run_id,
        dataset_id=dataset_id,
        question=question,
        profile=profile,
        messages=messages,
        max_steps=max_steps,
    ):
        if event["event"] == "step":
            steps += 1
        elif event["event"] == "answer":
            last_answer = event["data"]
        elif event["event"] == "error":
            last_error = event["data"]
    result = last_answer or {"run_id": run_id, "status": "failed", "error": (last_error or {}).get("error")}
    result.setdefault("step_count", steps)
    return result


def daily_cost_total(session, day: datetime | None = None) -> float:
    """Sum ``runs.cost_usd`` for a calendar day (running daily total)."""
    from sqlalchemy import func
    RunRow = _models().RunRow
    day = day or datetime.now(timezone.utc)
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    total = (
        session.query(func.coalesce(func.sum(RunRow.cost_usd), 0.0))
        .filter(RunRow.created_at >= start)
        .scalar()
    )
    return float(total or 0.0)


# --- persistence helpers ----------------------------------------------------


def _models():
    """Import the DB models by name at runtime (owned by the db-schema slice)."""
    import db.models as models
    return models


def _step_payload(node: str, state: dict, order: int, latency_ms: int) -> dict[str, Any]:
    exec_result = state.get("exec_result") or {}
    return {
        "step_index": order,
        "node": node,
        "label": _NODE_LABELS.get(node, node),
        "max_steps": state.get("max_steps"),
        "status": _step_status(node, state),
        "detail": _step_detail(node, state),
        "code": state.get("code") if node in ("generate_code", "execute") else None,
        "result_summary": _summary_text(exec_result.get("summary")) if node == "execute" else None,
        "latency_ms": latency_ms,
    }


def _step_status(node: str, state: dict) -> str:
    if node == "execute":
        exec_result = state.get("exec_result") or {}
        return "failed" if exec_result.get("error") else "worked"
    if state.get("error"):
        return "failed"
    return "worked"


def _step_detail(node: str, state: dict) -> str | None:
    if node == "plan":
        if state.get("needs_clarification"):
            return f"Needs clarification: {state.get('clarifying_question')}"
        return state.get("plan")
    if node == "inspect":
        return f"decision: {state.get('_inspect_decision')}"
    if node == "execute":
        exec_result = state.get("exec_result") or {}
        return exec_result.get("error") or "executed"
    if node == "finalize":
        return state.get("prose")
    if node == "clarify":
        return state.get("clarifying_question")
    return None


def _summary_text(summary: Any) -> str | None:
    if summary is None:
        return None
    try:
        return json.dumps(summary, default=str)[:4000]
    except (TypeError, ValueError):
        return str(summary)[:4000]


def _persist_step(run_id: str, order: int, node: str, state: dict, latency_ms: int) -> None:
    from db.session import create_db_session
    models = _models()
    payload = _step_payload(node, state, order, latency_ms)
    try:
        with create_db_session() as session:
            session.add(
                models.RunStepRow(
                    run_id=run_id,
                    step_index=order,
                    node=node,
                    status=payload["status"],
                    code=payload.get("code"),
                    result_summary=payload.get("result_summary"),
                    detail=(payload.get("detail") or "")[:8000] if payload.get("detail") else None,
                    latency_ms=latency_ms,
                )
            )
    except Exception as exc:  # persistence must not break the stream
        _log.error("persist_step_failed", run_id=run_id, node=node, error=str(exc))


def _persist_run(run_id: str, state: dict, *, status: str) -> None:
    from db.session import create_db_session
    models = _models()
    tokens = state.get("tokens") or {}
    try:
        with create_db_session() as session:
            run = session.get(models.RunRow, run_id)
            if run is None:
                _log.error("persist_run_missing", run_id=run_id)
                return
            run.status = status
            run.plan = state.get("plan")
            run.final_code = state.get("code")
            run.prose = state.get("prose")
            run.chart_json = _json_or_none(state.get("chart"))
            run.table_json = _json_or_none(state.get("table"))
            run.prompt_tokens = int(tokens.get("prompt", 0))
            run.completion_tokens = int(tokens.get("completion", 0))
            run.cost_usd = float(state.get("cost_usd", 0.0))
            run.step_count = state.get("step_index")
            run.error_message = state.get("error")
            run.completed_at = datetime.now(timezone.utc)
    except Exception as exc:
        _log.error("persist_run_failed", run_id=run_id, error=str(exc))


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return None


def _sse(event: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": event, "data": data}
