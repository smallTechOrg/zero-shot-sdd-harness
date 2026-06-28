"""Analysis endpoints: create a run, stream it (SSE), fetch it (Phase 1)."""
from __future__ import annotations

import json
import queue
import threading

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.models import DatasetRow, RunRow
from db.session import create_db_session, get_session
from graph import events_bus
from graph.runner import create_run_row, run_agent
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.analysis")


class RunRequest(BaseModel):
    question: str


def _dispatch_run(dataset_id: str, question: str, run_id: str) -> None:
    """Run the agent in a background thread so the POST returns immediately."""
    def _target() -> None:
        try:
            run_agent(dataset_id, question, run_id=run_id)
        except Exception as exc:  # last-resort guard — never crash the thread silently
            _log.error("dispatch_failed", run_id=run_id, error=str(exc))
            events_bus.publish(run_id, "error",
                               {"status": "failed", "error": str(exc)})
            events_bus.close_stream(run_id)

    threading.Thread(target=_target, daemon=True).start()


@router.post("/datasets/{dataset_id}/runs")
def create_run(
    dataset_id: str, req: RunRequest, session: Session = Depends(get_session)
) -> dict:
    if session.get(DatasetRow, dataset_id) is None:
        raise api_error("NOT_FOUND", f"Dataset {dataset_id} not found", 404)
    if not req.question or not req.question.strip():
        raise api_error("BAD_REQUEST", "Question must not be empty.", 400)

    run_id = create_run_row(dataset_id, req.question.strip())
    # Open the stream BEFORE dispatch so early events are not lost.
    events_bus.open_stream(run_id)
    _dispatch_run(dataset_id, req.question.strip(), run_id)
    return ok({"run_id": run_id, "status": "running"})


@router.get("/runs/{run_id}/stream")
def stream_run(run_id: str, session: Session = Depends(get_session)) -> StreamingResponse:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)

    q = events_bus.get_stream(run_id)

    def _event_gen():
        # If the run already finished (no live stream), replay a terminal event.
        if q is None:
            yield _terminal_from_db(run_id)
            return
        try:
            while True:
                try:
                    item = q.get(timeout=120)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                if item is events_bus.DONE:
                    break
                yield _sse(item["type"], item["payload"])
        finally:
            events_bus.drop_stream(run_id)

    return StreamingResponse(_event_gen(), media_type="text/event-stream")


def _terminal_from_db(run_id: str) -> str:
    with create_db_session() as s:
        run = s.get(RunRow, run_id)
        if run is None:
            return _sse("error", {"status": "failed", "error": "run not found"})
        if run.status == "completed":
            return _sse("final", {
                "status": "completed",
                "answer": run.answer,
                "chart_spec": json.loads(run.chart_spec_json) if run.chart_spec_json else None,
                "table": json.loads(run.table_json) if run.table_json else None,
                "code": _last_code(run),
            })
        return _sse("error", {"status": run.status,
                              "error": run.error_message or "Run failed."})


def _last_code(run: RunRow) -> str | None:
    try:
        steps = json.loads(run.steps_json) if run.steps_json else []
        return steps[-1]["code"] if steps else None
    except Exception:
        return None


def _sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)
    return ok({
        "run_id": run.id,
        "dataset_id": run.dataset_id,
        "question": run.question,
        "plan": run.plan,
        "status": run.status,
        "answer": run.answer,
        "chart_spec": json.loads(run.chart_spec_json) if run.chart_spec_json else None,
        "table": json.loads(run.table_json) if run.table_json else None,
        "steps": json.loads(run.steps_json) if run.steps_json else [],
        "tokens": run.tokens or 0,
        "error": run.error_message,
    })
