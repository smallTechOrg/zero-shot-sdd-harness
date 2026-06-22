from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session as DBSession

from analyst.api._common import api_error
from analyst.api.sessions import _resolve_or_create_session
from analyst.db.models import AuditLogRow
from analyst.db.session import get_session as get_db_session

router = APIRouter()


@router.get("/audit")
async def get_audit_log(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    db: DBSession = Depends(get_db_session),
):
    try:
        session, _, _ = _resolve_or_create_session(request, db, response)

        # Count total entries for this session
        total_stmt = (
            select(AuditLogRow)
            .where(AuditLogRow.session_id == session.session_id)
        )
        total = len(db.execute(total_stmt).all())

        # Fetch limited entries, most recent first
        stmt = (
            select(AuditLogRow)
            .where(AuditLogRow.session_id == session.session_id)
            .order_by(desc(AuditLogRow.timestamp))
            .limit(limit)
        )
        rows = db.execute(stmt).scalars().all()

        entries = [
            {
                "timestamp": row.timestamp.isoformat(),
                "session_id": row.session_id,
                "source_question": row.source_question,
                "sql": row.sql,
                "row_count": row.row_count,
                "status": row.status,
                "error_message": row.error_message,
            }
            for row in rows
        ]

        return {"entries": entries, "total": total}
    except Exception as e:
        return api_error("audit_read_failed", str(e), 500)
