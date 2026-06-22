from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DBSession

from analyst.api._common import api_error
from analyst.db.session import get_session as get_db_session
from analyst.errors import AnalystError
from analyst.services.session_store import create_session, get_session, update_session

router = APIRouter()


def _resolve_or_create_session(request: Request, db: DBSession, response: Response):
    """
    Read session_id from cookie; if found and valid return existing session.
    Otherwise create a new session, set cookie, and return it.
    Returns (session, session_id, is_new).
    """
    session_id = request.cookies.get("session_id")
    if session_id:
        session = get_session(session_id, db)
        if session is not None:
            return session, session_id, False

    # Create new session
    session = create_session(db)
    response.set_cookie(
        "session_id",
        session.session_id,
        httponly=True,
        samesite="strict",
    )
    return session, session.session_id, True


@router.post("/sessions")
async def create_new_session(
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db_session),
):
    try:
        session = create_session(db)
        response.set_cookie(
            "session_id",
            session.session_id,
            httponly=True,
            samesite="strict",
        )
        return {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
        }
    except Exception as e:
        return api_error("session_create_failed", str(e), 500)


@router.get("/sessions/current")
async def get_current_session(
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db_session),
):
    try:
        stub_mode = request.app.state.stub_mode
        session, _, _ = _resolve_or_create_session(request, db, response)
        data = session.model_dump(mode="json")
        data["stub_mode"] = stub_mode
        return data
    except Exception as e:
        return api_error("session_read_failed", str(e), 500)
