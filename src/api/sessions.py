import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from api._common import ok, api_error
from db.session import get_session
from db.models import Session, Message, Dataset
from graph.runner import run_query

router = APIRouter()


class QueryRequest(BaseModel):
    dataset_id: str
    question: str


@router.post("/sessions")
def create_session(session: DBSession = Depends(get_session)) -> dict:
    s = Session()
    session.add(s)
    session.flush()
    return ok({
        "id": s.id,
        "title": s.title,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    })


@router.get("/sessions")
def list_sessions(session: DBSession = Depends(get_session)) -> dict:
    rows = session.execute(
        select(Session).order_by(Session.updated_at.desc())
    ).scalars().all()
    return ok({
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in rows
        ]
    })


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: str, session: DBSession = Depends(get_session)) -> dict:
    if session.get(Session, session_id) is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found.", 404)
    rows = session.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    ).scalars().all()
    return ok({
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sql": m.sql,
                "result": json.loads(m.result_json) if m.result_json else None,
                "dataset_id": m.dataset_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ]
    })


@router.post("/sessions/{session_id}/query")
def query_session(
    session_id: str,
    req: QueryRequest,
    session: DBSession = Depends(get_session),
) -> dict:
    if session.get(Session, session_id) is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found.", 404)
    if session.get(Dataset, req.dataset_id) is None:
        raise api_error("NOT_FOUND", f"Dataset {req.dataset_id} not found.", 404)

    # Persist user message before invoking the graph.
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=req.question,
        dataset_id=req.dataset_id,
    )
    session.add(user_msg)
    s = session.get(Session, session_id)
    from db.models import _now
    s.updated_at = _now()
    session.commit()

    result = run_query(
        session_id=session_id,
        dataset_id=req.dataset_id,
        question=req.question,
    )

    if result.get("error"):
        raise api_error("QUERY_FAILED", result["error"], 400)

    return ok({
        "message_id": result["message_id"],
        "answer": result["answer"],
        "sql": result["sql"],
        "result": result["result"],
        "row_count": result["row_count"],
    })
