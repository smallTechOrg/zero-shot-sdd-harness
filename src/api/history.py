"""Audit-history endpoints.

- ``GET /datasets/{id}/runs`` — the per-dataset run list (browsable history).
- ``GET /runs/{id}``          — full detail of one run, including every step.
- ``GET /usage/today``        — the running daily cost/token/run-count total.

All responses are privacy-safe: they expose only audit metadata and aggregate
results (prose, chart spec, aggregate table) — never raw cell values.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api._common import api_error, ok
from db.models import DatasetRow, RunRow, RunStepRow
from db.session import get_session

router = APIRouter()


@router.get("/datasets/{dataset_id}/runs")
def list_runs(dataset_id: str, session: Session = Depends(get_session)) -> dict:
    if session.get(DatasetRow, dataset_id) is None:
        raise api_error("NOT_FOUND", f"Dataset {dataset_id} not found.", 404)
    stmt = (
        select(RunRow)
        .where(RunRow.dataset_id == dataset_id)
        .order_by(RunRow.created_at.desc())
    )
    runs = session.execute(stmt).scalars().all()
    return ok(
        {
            "runs": [
                {
                    "run_id": r.id,
                    "question": r.question,
                    "status": r.status,
                    "step_count": r.step_count or 0,
                    "cost_usd": float(r.cost_usd or 0.0),
                    "created_at": _iso(r.created_at),
                }
                for r in runs
            ]
        }
    )


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found.", 404)
    return ok(
        {
            "run_id": run.id,
            "dataset_id": run.dataset_id,
            "question": run.question,
            "status": run.status,
            "plan": run.plan,
            "final_code": run.final_code,
            "prose": run.prose,
            "chart": _json_or_none(run.chart_json),
            "table": _json_or_none(run.table_json),
            "tokens": {
                "prompt": run.prompt_tokens or 0,
                "completion": run.completion_tokens or 0,
            },
            "cost_usd": float(run.cost_usd or 0.0),
            "step_count": run.step_count or 0,
            "error_message": run.error_message,
            "created_at": _iso(run.created_at),
            "completed_at": _iso(run.completed_at),
            "steps": [
                {
                    "step_index": s.step_index,
                    "node": s.node,
                    "status": s.status,
                    "code": s.code,
                    "result_summary": s.result_summary,
                    "detail": s.detail,
                    "latency_ms": s.latency_ms,
                    "created_at": _iso(s.created_at),
                }
                for s in run.steps
            ],
        }
    )


@router.get("/usage/today")
def usage_today(session: Session = Depends(get_session)) -> dict:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    row = session.execute(
        select(
            func.coalesce(func.sum(RunRow.cost_usd), 0.0),
            func.coalesce(func.sum(RunRow.prompt_tokens), 0),
            func.coalesce(func.sum(RunRow.completion_tokens), 0),
            func.count(RunRow.id),
        ).where(RunRow.created_at >= start)
    ).one()
    total_cost, prompt_tokens, completion_tokens, run_count = row
    return ok(
        {
            "date": start.date().isoformat(),
            "total_cost_usd": float(total_cost or 0.0),
            "total_tokens": int((prompt_tokens or 0) + (completion_tokens or 0)),
            "run_count": int(run_count or 0),
        }
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _json_or_none(value: str | None):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None
