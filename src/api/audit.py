from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import select

from api._common import ok, api_error
from db.session import get_session
from db.models import AuditLogRow

router = APIRouter()


@router.get("/audit")
def list_audit(
    x_session_id: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    if not x_session_id:
        raise api_error("MISSING_SESSION", "X-Session-ID header is required", 400)

    rows = session.scalars(
        select(AuditLogRow)
        .where(AuditLogRow.session_id == x_session_id)
        .order_by(AuditLogRow.created_at.desc())
    ).all()

    entries = [
        {
            "id": row.id,
            "session_id": row.session_id,
            "dataset_table": row.dataset_table,
            "question": row.question,
            "sql_generated": row.sql_generated,
            "row_count": row.row_count,
            "duration_ms": row.duration_ms,
            "error": row.error,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]

    return ok(entries)
