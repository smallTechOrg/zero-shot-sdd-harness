"""Run endpoints: ask a question (synchronous agent run) + fetch a saved run."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import RunRow, DatasetRow
from domain.run import RunRequest, RunOut, KeyNumber
from graph.runner import run_analysis

router = APIRouter()


def _loads(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _run_out(run: RunRow) -> dict:
    key_numbers_raw = _loads(run.key_numbers_json, [])
    key_numbers = [
        KeyNumber(label=str(k.get("label", "")), value=str(k.get("value", "")))
        for k in key_numbers_raw
        if isinstance(k, dict)
    ]
    return RunOut(
        run_id=run.id,
        dataset_id=run.dataset_id,
        status=run.status,
        answer_text=run.answer_text,
        narrative=run.narrative,
        key_numbers=key_numbers,
        chart=_loads(run.chart_json, {}),
        table=_loads(run.table_json, []),
        code=run.generated_code or "",
        attempts=run.attempts or 0,
        error=run.error_message,
    ).model_dump()


@router.post("/runs")
def create_run(req: RunRequest, session: Session = Depends(get_session)) -> dict:
    if not req.dataset_id or not req.question or not req.question.strip():
        raise api_error("MISSING_FIELDS", "Both dataset_id and question are required.", 400)

    dataset = session.get(DatasetRow, req.dataset_id)
    if dataset is None:
        raise api_error("NOT_FOUND", f"Dataset {req.dataset_id} not found", 404)

    run_id = run_analysis(req.dataset_id, req.question)

    # The graph runs in its own DB sessions; expire this session's view so we
    # re-read the freshly-persisted run row.
    session.expire_all()
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("RUN_NOT_FOUND", "Run not found after execution", 500)

    # A failed run is returned as HTTP 200 with status="failed" + error in-body.
    return ok(_run_out(run))


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)
    return ok(_run_out(run))
