from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from data_analyst.api._common import api_error
from data_analyst.db.models import MessageRow, SessionRow
from data_analyst.db.session import create_db_session, get_session
from data_analyst.graph.runner import run_question

router = APIRouter()


class CreateSessionRequest(BaseModel):
    name: str


class AskRequest(BaseModel):
    question: str


@router.post("/sessions")
def create_session(body: CreateSessionRequest, db: Session = Depends(get_session)) -> dict:
    name = (body.name or "").strip()
    if not name:
        raise api_error("invalid_name", "Session name is required.", 400)
    row = SessionRow(name=name)
    db.add(row)
    db.flush()
    return {"id": row.id, "name": row.name, "created_at": row.created_at.isoformat()}


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_session)) -> dict:
    rows = db.query(SessionRow).order_by(SessionRow.updated_at.desc()).all()
    return {
        "sessions": [
            {"id": r.id, "name": r.name, "updated_at": r.updated_at.isoformat()}
            for r in rows
        ]
    }


@router.post("/sessions/{session_id}/ask")
def ask(session_id: int, body: AskRequest, db: Session = Depends(get_session)) -> dict:
    if db.get(SessionRow, session_id) is None:
        raise api_error("session_not_found", "Session not found.", 404)
    question = (body.question or "").strip()
    if not question:
        raise api_error("empty_question", "Question is required.", 400)

    # Persist the user turn and release the write before running the graph,
    # which opens its own sessions (SQLite allows only one writer at a time).
    with create_db_session() as writer:
        writer.add(MessageRow(session_id=session_id, role="user", content=question))

    result = run_question(session_id, question)
    return {
        "answer_text": result["answer_text"],
        "generated_sql": result["generated_sql"],
        "result_table": {
            "columns": result["result_columns"],
            "rows": result["result_rows"],
        },
        "audit_entry_id": result["audit_entry_id"],
        "status": result["status"],
    }
