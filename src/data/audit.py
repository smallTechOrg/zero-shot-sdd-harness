from db.models import AuditLogRow
from db.session import create_db_session


def log_operation(
    *,
    session_id: str | None,
    operation: str,
    question: str | None,
    sql_text: str | None,
    rows_returned: int | None,
    success: bool,
    error_message: str | None,
) -> None:
    """Persist one audit_log row."""
    with create_db_session() as session:
        session.add(
            AuditLogRow(
                session_id=session_id,
                operation=operation,
                question=question,
                sql_text=sql_text,
                rows_returned=rows_returned,
                success=success,
                error_message=error_message,
            )
        )
