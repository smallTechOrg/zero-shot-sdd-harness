from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from data_analyst.api._common import api_error
from data_analyst.db.models import AuditLogEntryRow, SessionRow
from data_analyst.db.session import get_session

router = APIRouter()


@router.get("/sessions/{session_id}/audit")
def view_audit(session_id: int, db: Session = Depends(get_session)) -> dict:
    if db.get(SessionRow, session_id) is None:
        raise api_error("session_not_found", "Session not found.", 404)
    rows = (
        db.query(AuditLogEntryRow)
        .filter(AuditLogEntryRow.session_id == session_id)
        .order_by(AuditLogEntryRow.created_at.desc())
        .all()
    )
    return {
        "entries": [
            {
                "id": r.id,
                "nl_prompt": r.nl_prompt,
                "generated_sql": r.generated_sql,
                "row_count": r.row_count,
                "duration_ms": r.duration_ms,
                "status": r.status,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
