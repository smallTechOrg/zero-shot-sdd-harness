import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datachat.api._common import ok, api_error
from datachat.db.models import SessionRow, MessageRow
from datachat.db.session import get_session, create_db_session

router = APIRouter(prefix="/api")


class QuestionRequest(BaseModel):
    question: str


@router.post("/sessions/{session_id}/messages")
def ask_question(
    session_id: str,
    body: QuestionRequest,
    db: Session = Depends(get_session),
):
    row = db.get(SessionRow, session_id)
    if not row:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)
    if row.status != "ready":
        raise api_error("SESSION_NOT_READY", f"Session status is {row.status}", 400)

    # Persist user message
    user_msg = MessageRow(session_id=session_id, role="user", content=body.question)
    db.add(user_msg)
    db.commit()

    # Load or restore the DataFrame
    from datachat.graph.nodes import _dataframe_store
    import io
    import pandas as pd

    df = _dataframe_store.get(session_id)
    if df is None:
        raise api_error("SESSION_DATA_LOST", "Session data is no longer in memory — please re-upload the file", 410)

    from datachat.graph.runner import run_agent
    result = run_agent(session_id, body.question, df)

    return ok({
        "answer": result["answer"],
        "reasoning_trace": result["reasoning_trace"],
        "llm_provider": result["llm_provider"],
    })


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, db: Session = Depends(get_session)):
    row = db.get(SessionRow, session_id)
    if not row:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    msgs = (
        db.query(MessageRow)
        .filter(MessageRow.session_id == session_id)
        .order_by(MessageRow.created_at)
        .all()
    )
    return ok([
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "reasoning_trace": json.loads(m.reasoning_trace) if m.reasoning_trace else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ])
