from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from data_analyst.api._common import render
from data_analyst.api.datasets import upload_dataset
from data_analyst.db.models import (
    AuditLogEntryRow,
    DatasetRow,
    MessageRow,
    SessionRow,
)
from data_analyst.db.session import get_session
from data_analyst.graph.runner import run_question
from data_analyst.observability import get_logger

router = APIRouter()
log = get_logger("data_analyst.web")


@router.get("/")
def home(request: Request, db: Session = Depends(get_session)):
    sessions = db.query(SessionRow).order_by(SessionRow.updated_at.desc()).all()
    return render(request, "home.html", sessions=sessions)


@router.post("/sessions/new")
def create_session_form(name: str = Form(...), db: Session = Depends(get_session)):
    label = (name or "").strip() or "Untitled session"
    row = SessionRow(name=label)
    db.add(row)
    db.flush()
    return RedirectResponse(f"/sessions/{row.id}", status_code=303)


@router.get("/sessions/{session_id}")
def session_view(session_id: int, request: Request, db: Session = Depends(get_session)):
    sess = db.get(SessionRow, session_id)
    if sess is None:
        return render(request, "error.html", detail="Session not found.")
    datasets = (
        db.query(DatasetRow).filter(DatasetRow.session_id == session_id).all()
    )
    messages = (
        db.query(MessageRow)
        .filter(MessageRow.session_id == session_id)
        .order_by(MessageRow.created_at.asc())
        .all()
    )
    audit = (
        db.query(AuditLogEntryRow)
        .filter(AuditLogEntryRow.session_id == session_id)
        .order_by(AuditLogEntryRow.created_at.desc())
        .all()
    )
    return render(
        request,
        "session.html",
        session=sess,
        datasets=datasets,
        messages=messages,
        audit=audit,
    )


@router.post("/sessions/{session_id}/upload")
async def upload_form(
    session_id: int,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_session),
):
    try:
        await upload_dataset(session_id, file=file, name=name, db=db)
    except Exception as exc:  # noqa: BLE001 — surface via redirect, never 500 the page
        log.error("web.upload_failed", error=str(exc))
    return RedirectResponse(f"/sessions/{session_id}", status_code=303)


@router.post("/sessions/{session_id}/chat")
def chat_form(
    session_id: int,
    request: Request,
    question: str = Form(...),
    db: Session = Depends(get_session),
):
    sess = db.get(SessionRow, session_id)
    if sess is None:
        return render(request, "error.html", detail="Session not found.")
    q = (question or "").strip()
    if q:
        from data_analyst.db.session import create_db_session

        with create_db_session() as writer:
            writer.add(MessageRow(session_id=session_id, role="user", content=q))
        run_question(session_id, q)
    return RedirectResponse(f"/sessions/{session_id}", status_code=303)
