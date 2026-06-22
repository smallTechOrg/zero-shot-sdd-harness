import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from analyst.api._common import api_error
from analyst.api.sessions import _resolve_or_create_session
from analyst.config.settings import get_settings
from analyst.db.session import get_session as get_db_session
from analyst.domain.audit import AuditLogEntry
from analyst.domain.session import ConversationTurn
from analyst.errors import AnalystError
from analyst.services.audit_service import append_audit_entry
from analyst.services.nl_query import generate_sql_for_question
from analyst.services.query_engine import execute_query
from analyst.services.session_store import update_session

router = APIRouter()

_SYSTEM_TEMPLATE: str | None = None


def _load_system_template() -> str:
    global _SYSTEM_TEMPLATE
    if _SYSTEM_TEMPLATE is None:
        prompt_path = Path(__file__).parent.parent / "prompts" / "nl_to_sql.md"
        _SYSTEM_TEMPLATE = prompt_path.read_text(encoding="utf-8")
    return _SYSTEM_TEMPLATE


class QueryRequest(BaseModel):
    question: str


@router.post("/query")
async def run_query(
    body: QueryRequest,
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db_session),
):
    question = body.question.strip()
    if not question:
        return api_error("bad_request", "question field is required and must not be empty", 400)

    try:
        session, _, _ = _resolve_or_create_session(request, db, response)
        settings = get_settings()
        llm_provider = request.app.state.llm_provider
        system_template = _load_system_template()

        if not session.datasets:
            return api_error(
                "no_datasets",
                "Session has no datasets loaded. Upload a dataset before querying.",
                422,
            )

        sql = generate_sql_for_question(
            question, session.datasets, llm_provider, system_template
        )

        result = execute_query(sql, session.datasets, settings)

        turn_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        user_turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            role="user",
            content=question,
            sql=None,
            result_summary=None,
            timestamp=now,
        )
        result_summary = f"Returned {result['row_count']} row(s)."
        assistant_turn = ConversationTurn(
            turn_id=turn_id,
            role="assistant",
            content=result_summary,
            sql=sql,
            result_summary=result_summary,
            timestamp=now,
        )
        session.conversation.append(user_turn)
        session.conversation.append(assistant_turn)
        update_session(session, db)

        audit_entry = AuditLogEntry(
            timestamp=now,
            session_id=session.session_id,
            source_question=question,
            sql=sql,
            row_count=result["row_count"],
            status="success",
            error_message=None,
        )
        append_audit_entry(audit_entry, db)

        return {
            "turn_id": turn_id,
            "sql": sql,
            "columns": result["columns"],
            "rows": result["rows"],
            "row_count": result["row_count"],
            "truncated": result["truncated"],
            "total_row_count": result["total_row_count"],
        }

    except AnalystError as e:
        # Write error audit entry when possible
        try:
            session_id_for_audit = request.cookies.get("session_id", "unknown")
            audit_entry = AuditLogEntry(
                timestamp=datetime.now(timezone.utc),
                session_id=session_id_for_audit,
                source_question=question,
                sql="",
                row_count=0,
                status="error",
                error_message=e.message,
            )
            append_audit_entry(audit_entry, db)
        except Exception:
            pass
        return api_error(e.code, e.message, e.status_code)
    except Exception as e:
        return api_error("internal_error", str(e), 500)
