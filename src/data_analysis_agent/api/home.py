from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from data_analysis_agent.api import templates
from data_analysis_agent.api._common import render
from data_analysis_agent.api._repository import attached_servers, query_count
from data_analysis_agent.config.settings import get_settings
from data_analysis_agent.db.models import McpServerRow, McpPromptRow, McpResourceRow, McpToolRow, SessionRow
from data_analysis_agent.db.session import get_session
from data_analysis_agent.tools.connectors.uri import DatasetURI

router = APIRouter()


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    """Render the home page listing all MCP servers and sessions."""
    rows = session.query(McpServerRow).order_by(McpServerRow.created_at.desc()).all()
    servers = [_server_view(session, s) for s in rows]
    sessions = session.query(SessionRow).order_by(SessionRow.updated_at.desc()).all()
    session_servers, session_query_counts = _session_overview(session, sessions)
    return render(
        request, templates, "home.html",
        servers=servers,
        all_sessions=sessions,
        session_servers=session_servers,
        session_query_counts=session_query_counts,
        enable_external=get_settings().enable_external_datasets,
    )


def _server_view(db: Session, server: McpServerRow) -> dict:
    """Build a credential-free per-server view-model for the home page."""
    tables = server.physical_tables
    return {
        "id": server.id,
        "name": server.name,
        "title": server.title,
        "type": server.type,
        "is_parquet": (server.type or "").lower() == "parquet",
        "uri_display": DatasetURI(server.uri).display(),
        "version": server.version,
        "table_count": len(tables),
        "total_rows": sum(t.get("row_count") or 0 for t in tables),
        "tool_count": _active_count(db, McpToolRow, server.id),
        "resource_count": _active_count(db, McpResourceRow, server.id),
        "prompt_count": _active_count(db, McpPromptRow, server.id),
        "last_sync_status": server.last_sync_status,
        "last_synced_at": server.last_synced_at,
        "connection_error": server.connection_error,
    }


def _active_count(db: Session, model, server_id: str) -> int:
    return (
        db.query(model)
        .filter(model.server_id == server_id, model.deleted_at.is_(None))
        .count()
    )


def _session_overview(
    db: Session, sessions: list[SessionRow]
) -> tuple[dict[str, list[McpServerRow]], dict[str, int]]:
    """Build per-session attached-server lists and question counts for the home view."""
    servers_by_session = {s.id: attached_servers(db, s.id) for s in sessions}
    count_by_session = {s.id: query_count(db, s.id) for s in sessions}
    return servers_by_session, count_by_session
