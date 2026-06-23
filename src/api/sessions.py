import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import SessionRow, DatasetRow, QaTurnRow
from domain.analyst import AskRequest
from graph.runner import run_analyst

router = APIRouter()


def _latest_dataset(session: Session, session_id: str) -> DatasetRow | None:
    return session.scalars(
        select(DatasetRow)
        .where(DatasetRow.session_id == session_id)
        .order_by(DatasetRow.created_at.desc())
    ).first()


@router.post("/sessions/{session_id}/ask")
def ask(session_id: str, req: AskRequest, session: Session = Depends(get_session)) -> dict:
    question = (req.question or "").strip()
    if not question:
        raise api_error("BAD_REQUEST", "Question must not be empty.", 400)

    if session.get(SessionRow, session_id) is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)
    if _latest_dataset(session, session_id) is None:
        raise api_error("NOT_FOUND", "Session has no dataset.", 404)

    # Failed turns (guard/SQL/LLM error) return HTTP 200 with status="failed".
    outcome = run_analyst(session_id, question)
    return ok(outcome)


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(SessionRow, session_id)
    if row is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    dataset = _latest_dataset(session, session_id)
    dataset_payload = None
    if dataset is not None:
        dataset_payload = {
            "dataset_id": dataset.id,
            "table_name": dataset.table_name,
            "row_count": dataset.row_count,
            "columns": json.loads(dataset.columns_json),
        }

    turns = session.scalars(
        select(QaTurnRow)
        .where(QaTurnRow.session_id == session_id)
        .order_by(QaTurnRow.created_at.asc())
    ).all()
    turn_payload = [
        {
            "turn_id": t.id,
            "question": t.question,
            "answer_text": t.answer_text,
            "sql_text": t.sql_text,
            "result": json.loads(t.result_json) if t.result_json else None,
            "status": t.status,
            "error": t.error_message,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in turns
    ]

    return ok(
        {
            "session_id": row.id,
            "title": row.title,
            "dataset": dataset_payload,
            "turns": turn_payload,
        }
    )
