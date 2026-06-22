from typing import Optional
from fastapi import APIRouter, Query

from data_analyst.api._common import ok
from data_analyst.audit.logger import AuditLogger
from data_analyst.config.settings import get_settings

router = APIRouter()


@router.get("/audit")
def get_audit_log(
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    settings = get_settings()
    audit = AuditLogger(settings.resolved_data_dir)
    entries = audit.read_recent(session_id=session_id, limit=limit)
    return ok(entries)
