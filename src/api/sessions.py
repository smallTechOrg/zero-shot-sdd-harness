"""Session endpoints: create a session (loads a dataset for a conversation) and
fetch it with its run history. Conversation memory is threaded into follow-up
questions by the runner from the session's completed runs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import SessionRow, DatasetRow, RunRow
from domain.session import SessionCreate, SessionOut
from domain.run import RunSummary

router = APIRouter()


def _run_summary(run: RunRow) -> RunSummary:
    return RunSummary(
        run_id=run.id,
        question=run.question,
        status=run.status,
        created_at=run.created_at.isoformat() if run.created_at else None,
        tokens_used=run.tokens_used,
        cost_estimate_usd=run.cost_estimate_usd,
    )


@router.post("/sessions")
def create_session(req: SessionCreate, session: Session = Depends(get_session)) -> dict:
    if not req.dataset_id:
        raise api_error("MISSING_FIELDS", "dataset_id is required.", 400)

    ds = session.get(DatasetRow, req.dataset_id)
    if ds is None:
        raise api_error("NOT_FOUND", f"Dataset {req.dataset_id} not found", 404)

    row = SessionRow(dataset_id=req.dataset_id)
    session.add(row)
    session.flush()

    out = SessionOut(
        id=row.id,
        dataset_id=row.dataset_id,
        created_at=row.created_at.isoformat() if row.created_at else None,
        runs=[],
    )
    return ok(out.model_dump())


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(SessionRow, session_id)
    if row is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    runs = session.execute(
        select(RunRow)
        .where(RunRow.session_id == session_id)
        .order_by(RunRow.created_at.desc())
    ).scalars().all()

    out = SessionOut(
        id=row.id,
        dataset_id=row.dataset_id,
        created_at=row.created_at.isoformat() if row.created_at else None,
        runs=[_run_summary(r) for r in runs],
    )
    return ok(out.model_dump())
