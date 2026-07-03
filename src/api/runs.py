"""Run endpoints: ask a question, fetch/list saved runs, and re-run a saved one."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import RunRow, DatasetRow
from domain.run import RunRequest, RunOut, RunSummary, KeyNumber
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
        session_id=run.session_id,
        tokens_used=run.tokens_used,
        cost_estimate_usd=run.cost_estimate_usd,
        created_at=run.created_at.isoformat() if run.created_at else None,
    ).model_dump()


def _run_summary(run: RunRow) -> dict:
    return RunSummary(
        run_id=run.id,
        question=run.question,
        status=run.status,
        created_at=run.created_at.isoformat() if run.created_at else None,
        tokens_used=run.tokens_used,
        cost_estimate_usd=run.cost_estimate_usd,
    ).model_dump()


@router.post("/runs")
def create_run(req: RunRequest, session: Session = Depends(get_session)) -> dict:
    if not req.dataset_id or not req.question or not req.question.strip():
        raise api_error("MISSING_FIELDS", "Both dataset_id and question are required.", 400)

    dataset = session.get(DatasetRow, req.dataset_id)
    if dataset is None:
        raise api_error("NOT_FOUND", f"Dataset {req.dataset_id} not found", 404)

    run_id = run_analysis(
        req.dataset_id,
        req.question,
        session_id=req.session_id,
        run_id=req.run_id,
    )

    # The graph runs in its own DB sessions; expire this session's view so we
    # re-read the freshly-persisted run row.
    session.expire_all()
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("RUN_NOT_FOUND", "Run not found after execution", 500)

    # A failed run is returned as HTTP 200 with status="failed" + error in-body.
    return ok(_run_out(run))


@router.get("/runs")
def list_runs(
    dataset_id: str | None = None,
    session_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    query = select(RunRow)
    if dataset_id:
        query = query.where(RunRow.dataset_id == dataset_id)
    if session_id:
        query = query.where(RunRow.session_id == session_id)
    query = query.order_by(RunRow.created_at.desc())
    rows = session.execute(query).scalars().all()
    return ok([_run_summary(r) for r in rows])


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)
    return ok(_run_out(run))


@router.post("/runs/{run_id}/rerun")
def rerun_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    saved = session.get(RunRow, run_id)
    if saved is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)

    # Create a NEW run (new id) against the current data — the original is never
    # mutated so results can be compared over time.
    new_run_id = run_analysis(
        saved.dataset_id,
        saved.question,
        session_id=saved.session_id,
    )

    session.expire_all()
    new_run = session.get(RunRow, new_run_id)
    if new_run is None:
        raise api_error("RUN_NOT_FOUND", "Run not found after execution", 500)
    return ok(_run_out(new_run))
