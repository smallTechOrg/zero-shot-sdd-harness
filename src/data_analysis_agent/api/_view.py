"""Shared view-model builders for the single-page shell.

`/`, `/sessions/{id}` and `/database/{id}` all render the same ``index.html`` with a different active
entity. The shell itself carries only **counts** (for headers) and the active entity's **metadata** — the
actual list rows (sessions, databases, the chat thread, and the capability lists) are fetched by AJAX
**after** the shell renders, each as its own keyset-paginated page (see ``cursor_*`` below and the
relocated fragment endpoints in ``api/{sessions,database,queries}.py``). Every dataset URI is rendered
credential-free via :meth:`DatasetURI.display`.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from data_analysis_agent.api._pagination import keyset_page
from data_analysis_agent.api._repository import attached_databases, query_count
from data_analysis_agent.config.settings import get_settings
from data_analysis_agent.tools.connectors.base import DATABASE_TYPES
from data_analysis_agent.db.models import (
    McpPromptRow,
    McpResourceRow,
    DatabaseRow,
    McpToolRow,
    QueryRecordRow,
    SessionRow,
)
from data_analysis_agent.tools.connectors.uri import DatasetURI


def _active_count(db: Session, model, database_id: str) -> int:
    return (
        db.query(model)
        .filter(model.database_id == database_id, model.deleted_at.is_(None))
        .count()
    )


def _active_rows(db: Session, model, database_id: str) -> list:
    return (
        db.query(model)
        .filter(model.database_id == database_id, model.deleted_at.is_(None))
        .order_by(model.created_at, model.id)
        .all()
    )


def _entity_tables(resources: list) -> list[dict]:
    """Project the entity (non-schema) resources to table dicts (the per-table schema source of truth).

    Each entity resource's ``content`` is ``{table, columns, row_count}``; columns are the table's schema.
    """
    tables: list[dict] = []
    for r in resources:
        if r.kind == "schema":
            continue
        content = r.content or {}
        columns = content.get("columns") or []
        tables.append({
            "table_name": content.get("table") or r.name,
            "column_names": [c.get("name") for c in columns],
            "schema": columns,
            "row_count": content.get("row_count"),
        })
    return tables


def server_card_view(db: Session, server: DatabaseRow) -> dict:
    """A credential-free summary of one database for the Databases card (one paged row)."""
    resources = _active_rows(db, McpResourceRow, server.id)
    tables = _entity_tables(resources)
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
        "resource_count": len(resources),
        "prompt_count": _active_count(db, McpPromptRow, server.id),
        "last_sync_status": server.last_sync_status,
        "last_synced_at": server.last_synced_at,
        "connection_error": server.connection_error,
    }


def session_card_view(db: Session, sess: SessionRow, active_id: str | None) -> dict:
    """A summary of one session for the sidebar list (one paged row)."""
    servers = attached_databases(db, sess.id)
    return {
        "id": sess.id,
        "name": sess.name or "Untitled session",
        "server_names": [s.name for s in servers],
        "query_count": query_count(db, sess.id),
        "created_at": sess.created_at,
        "updated_at": sess.updated_at,
        "is_active": sess.id == active_id,
    }


# --- keyset (cursor) windows for the AJAX-loaded lists -----------------------

def cursor_sessions(db: Session, cursor: str | None, active_id: str | None) -> tuple[list[dict], str | None]:
    """One keyset window of session cards, most-recently-updated first."""
    rows, next_cursor = keyset_page(
        db.query(SessionRow), sort_col=SessionRow.updated_at, id_col=SessionRow.id,
        sort_attr="updated_at", cursor=cursor, limit=get_settings().ui_page_size, descending=True,
    )
    return [session_card_view(db, s, active_id) for s in rows], next_cursor


def cursor_databases(db: Session, cursor: str | None) -> tuple[list[dict], str | None]:
    """One keyset window of database cards, newest first."""
    rows, next_cursor = keyset_page(
        db.query(DatabaseRow), sort_col=DatabaseRow.created_at, id_col=DatabaseRow.id,
        sort_attr="created_at", cursor=cursor, limit=get_settings().ui_page_size, descending=True,
    )
    return [server_card_view(db, s) for s in rows], next_cursor


def cursor_queries(db: Session, session_id: str, cursor: str | None) -> tuple[list[QueryRecordRow], str | None]:
    """One keyset window of a session's chat thread.

    Windows are taken newest-first (so page 1 is the latest turns) but each window is returned
    **chronological** (oldest→newest) for display, with the freshest turn at the bottom. ``next_cursor``
    walks toward OLDER turns (the "Next" page in cursor order)."""
    rows, next_cursor = keyset_page(
        db.query(QueryRecordRow).filter(QueryRecordRow.session_id == session_id),
        sort_col=QueryRecordRow.created_at, id_col=QueryRecordRow.id,
        sort_attr="created_at", cursor=cursor, limit=get_settings().ui_page_size, descending=True,
    )
    return list(reversed(rows)), next_cursor


# --- shell context (counts + active-entity metadata only) --------------------

def server_detail_view(db: Session, server: DatabaseRow) -> dict:
    """Database-tab metadata + counts + the EER source. Capability ROWS are loaded by AJAX from the
    JSON-RPC surface (``POST /database/{id}`` ``*/list``); only the totals (for the section headers) and
    the EER diagram (fed from ALL entity resources — never paginated) are server-rendered here."""
    all_resources = _active_rows(db, McpResourceRow, server.id)  # full set: EER + schema + total count
    schema_res = next((r for r in all_resources if r.kind == "schema"), None)
    return {
        "id": server.id,
        "name": server.name,
        "title": server.title,
        "description": server.description,
        "type": server.type,
        "is_parquet": (server.type or "").lower() == "parquet",
        "uri_display": DatasetURI(server.uri).display(),
        "version": server.version,
        "last_sync_status": server.last_sync_status,
        "last_synced_at": server.last_synced_at,
        "connection_error": server.connection_error,
        "tables": _entity_tables(all_resources),        # per-table schema from the entity resources (full)
        "dataset_schema": (schema_res.content if schema_res else {}),  # from the schema resource
        "tool_count": _active_count(db, McpToolRow, server.id),
        "resource_count": len(all_resources),
        "prompt_count": _active_count(db, McpPromptRow, server.id),
    }


def _server_options(db: Session) -> list[dict]:
    """Lightweight full list of databases for the new-session picker + the Database-tab quick-pick.

    Not paginated (it's a form picker, not a list view); carries only what those two spots render.
    """
    out: list[dict] = []
    for s in db.query(DatabaseRow).order_by(DatabaseRow.created_at.desc()).all():
        table_count = (
            db.query(McpResourceRow)
            .filter(McpResourceRow.database_id == s.id, McpResourceRow.deleted_at.is_(None),
                    McpResourceRow.kind != "schema")
            .count()
        )
        out.append({"id": s.id, "name": s.name, "table_count": table_count, "version": s.version})
    return out


def spa_context(
    db: Session,
    *,
    active_tab: str = "analyse",
    active_session: SessionRow | None = None,
    active_server: DatabaseRow | None = None,
    new_record_id: str | None = None,
) -> dict:
    """Assemble the shared shell context: header counts, the server picker, and the active entity's
    metadata. List ROWS are NOT here — the client fetches each list by AJAX after render."""
    ctx: dict = {
        "servers": _server_options(db),               # picker (modal + quick-pick) only
        "server_total": db.query(DatabaseRow).count(),
        "session_total": db.query(SessionRow).count(),
        "page_size": get_settings().ui_page_size,
        "active_tab": active_tab,
        "active_session": None,
        "active_server": None,
        "new_record_id": new_record_id,
        "new_record_status": None,
        "llm_model": get_settings().llm_model,
        "database_types": [{"value": v, "label": label, "external": ext, "hint": hint}
                           for v, label, ext, hint in DATABASE_TYPES],
    }
    if active_session is not None:
        ctx["active_session"] = {
            "id": active_session.id,
            "name": active_session.name or "Untitled session",
            "servers": attached_databases(db, active_session.id),
        }
        if new_record_id:
            rec = db.get(QueryRecordRow, new_record_id)
            ctx["new_record_status"] = rec.status if rec else None
    if active_server is not None:
        ctx["active_server"] = server_detail_view(db, active_server)
    return ctx
