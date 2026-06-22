import sys

from sqlalchemy.orm import Session as DBSession

from analyst.db.models import AuditLogRow
from analyst.domain.audit import AuditLogEntry


def append_audit_entry(entry: AuditLogEntry, db: DBSession) -> None:
    """Write audit entry. Failure logs to stderr but does not propagate."""
    try:
        row = AuditLogRow(
            timestamp=entry.timestamp,
            session_id=entry.session_id,
            source_question=entry.source_question,
            sql=entry.sql,
            row_count=entry.row_count,
            status=entry.status,
            error_message=entry.error_message,
        )
        db.add(row)
        db.commit()
    except Exception as e:
        print(f"[audit] write failed: {e}", file=sys.stderr)
