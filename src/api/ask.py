"""Streaming ``POST /datasets/{id}/ask`` — SSE live steps + final answer.

Creates a ``runs`` row, seeds conversation ``messages`` from prior runs of the
same dataset (so follow-ups understand context), then drives the streaming
graph runner and forwards each event over Server-Sent Events.

The runner's ``answer`` event is adapted here to the frontend contract:
- ``chart`` is reshaped from the graph's ``{type, x_key, y_key, data}`` to
  ``{type, x, y, data}``;
- ``daily_total_usd`` is computed (the runner does not emit it);
- ``uncertainty`` is forwarded (null when the run did not hit the step limit).
The graph itself is never modified — adaptation lives in this API layer only.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from api._common import api_error
from db.models import DatasetRow, RunRow
from db.session import create_db_session, get_session
from graph.runner import daily_cost_total, stream_run
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.ask")

# How many prior turns to seed as conversation memory.
_MAX_HISTORY_TURNS = 6


@router.post("/datasets/{dataset_id}/ask")
def ask(dataset_id: str, body: dict, session: Session = Depends(get_session)) -> EventSourceResponse:
    dataset = session.get(DatasetRow, dataset_id)
    if dataset is None:
        raise api_error("NOT_FOUND", f"Dataset {dataset_id} not found.", 404)

    question = (body or {}).get("question")
    if not isinstance(question, str) or not question.strip():
        raise api_error("BAD_REQUEST", "Question must be a non-empty string.", 400)
    question = question.strip()

    profile = json.loads(dataset.profile_json)
    messages = _seed_messages(session, dataset_id)

    # Create the run row up front so the streaming runner can update it.
    run = RunRow(dataset_id=dataset_id, question=question, status="pending")
    session.add(run)
    session.flush()
    run_id = run.id
    # Commit so the runner's own session (a separate connection) sees the row.
    session.commit()

    _log.info("ask_started", run_id=run_id, dataset_id=dataset_id, question=question[:200])

    def event_generator():
        for event in stream_run(
            run_id=run_id,
            dataset_id=dataset_id,
            question=question,
            profile=profile,
            messages=messages,
        ):
            name = event["event"]
            data = event["data"]
            if name == "answer":
                data = _adapt_answer(data)
            yield {"event": name, "data": json.dumps(data, default=str)}

    return EventSourceResponse(event_generator())


def _seed_messages(session: Session, dataset_id: str) -> list[dict]:
    """Build conversation memory from prior completed runs of this dataset."""
    stmt = (
        select(RunRow)
        .where(RunRow.dataset_id == dataset_id)
        .order_by(RunRow.created_at.asc())
    )
    runs = session.execute(stmt).scalars().all()
    messages: list[dict] = []
    for r in runs:
        if not r.question:
            continue
        messages.append({"role": "user", "content": r.question})
        if r.prose:
            messages.append({"role": "assistant", "content": r.prose})
    # Keep only the most recent turns (each turn ~= 2 messages).
    return messages[-(_MAX_HISTORY_TURNS * 2):]


def _adapt_answer(data: dict) -> dict:
    """Reshape the runner's answer dict to the frontend answer contract."""
    out = dict(data)
    out["chart"] = _adapt_chart(data.get("chart"))
    out.setdefault("uncertainty", data.get("uncertainty"))
    out["daily_total_usd"] = _daily_total()
    return out


def _adapt_chart(chart: dict | None) -> dict | None:
    """Map the graph chart spec ({type, x_key, y_key, data}) → {type, x, y, data}."""
    if not isinstance(chart, dict):
        return None
    return {
        "type": chart.get("type"),
        "x": chart.get("x_key") or chart.get("x"),
        "y": chart.get("y_key") or chart.get("y"),
        "data": chart.get("data", []),
        "title": chart.get("title", ""),
    }


def _daily_total() -> float:
    try:
        with create_db_session() as s:
            return daily_cost_total(s)
    except Exception as exc:  # never break the stream on a meter read
        _log.error("daily_total_failed", error=str(exc))
        return 0.0
