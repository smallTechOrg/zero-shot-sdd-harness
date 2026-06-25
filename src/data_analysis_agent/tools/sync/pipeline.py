"""Sync orchestration: run the 5 stages, then apply the result (versioned, soft-delete-only)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from data_analysis_agent.db.models import (
    McpPromptRow,
    McpResourceRow,
    McpServerRow,
    McpToolRow,
)
from data_analysis_agent.tools.mcp.server import (
    new_connection,
    register_parquet_view,
    _run_select_params,
)
from data_analysis_agent.tools.sync import stages

log = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SyncResult:
    """The capabilities a sync run proposes for a server."""

    title: str
    description: str
    dataset_schema: dict
    resources: list[dict]
    tools: list[dict]
    prompts: list[dict]
    status: str  # "ok" | "partial"


# --- Run --------------------------------------------------------------------

def run_sync(db: Session, server: McpServerRow) -> SyncResult:
    """Run the 5 LLM stages over the server's data + existing capabilities. Never raises."""
    name = server.name
    tables = server.physical_tables
    active = _active(db, server.id)

    td = stages.stage_title(name, tables, {"title": server.title, "description": server.description})
    schema = stages.stage_schema(name, tables, server.dataset_schema)
    entities = stages.stage_entities(name, schema, _meta(active["resources"], "uri", "name"))
    tools = stages.stage_tools(name, entities, tables, _meta(active["tools"], "name"))
    prompts = stages.stage_prompts(name, tools, _meta(active["prompts"], "name"))

    tools, dropped = _validate_tools(server, tables, tools)
    resources = [_schema_resource(name, schema)] + [_entity_resource(name, e) for e in entities]
    status = "partial" if dropped else "ok"
    log.info("sync.run", server=name, tools=len(tools), resources=len(resources), prompts=len(prompts),
             status=status)
    return SyncResult(td["title"], td["description"], schema, resources, tools, prompts, status)


# --- Apply (transactional, versioned, soft-delete-only) ---------------------

def apply_sync_result(db: Session, server: McpServerRow, result: SyncResult) -> None:
    """Apply a :class:`SyncResult`: insert/update/soft-delete children + bump version.

    Runs in the caller's transaction (the caller commits). Never hard-deletes a capability.
    """
    new_version = (server.version or 1) + 1
    active = _active(db, server.id)
    _apply(db, server.id, new_version, result.tools, active["tools"], "name", _tool_fields)
    _apply(db, server.id, new_version, result.resources, active["resources"], "uri", _resource_fields)
    _apply(db, server.id, new_version, result.prompts, active["prompts"], "name", _prompt_fields)
    server.version = new_version
    server.title = result.title
    server.description = result.description
    server.dataset_schema = result.dataset_schema
    server.last_synced_at = _now()
    server.last_sync_status = result.status


def _apply(db, server_id, new_version, proposed, active_rows, key, set_fields):
    """Generic diff-apply: match by ``key`` → update; new → insert; missing → soft-delete."""
    by_key = {getattr(r, key): r for r in active_rows}
    seen: set[str] = set()
    for item in proposed:
        k = item.get(key)
        if not k or k in seen:
            continue
        seen.add(k)
        existing = by_key.get(k)
        if existing is not None:
            set_fields(existing, item)
        else:
            new_row = _new_row_for(set_fields)
            new_row.server_id = server_id
            new_row.created_version = new_version
            set_fields(new_row, item)
            db.add(new_row)
    for k, row in by_key.items():
        if k not in seen:
            row.deleted_at = _now()
            row.deleted_version = new_version


def _new_row_for(set_fields):
    return {_tool_fields: McpToolRow, _resource_fields: McpResourceRow, _prompt_fields: McpPromptRow}[set_fields]()


def _tool_fields(row: McpToolRow, item: dict) -> None:
    row.name = item["name"]
    row.title = item.get("title")
    row.description = item.get("description") or ""
    row.input_schema_json = json.dumps(item.get("input_schema") or {"type": "object", "properties": {}})
    row.output_schema_json = json.dumps(item["output_schema"]) if item.get("output_schema") else None
    row.annotations_json = json.dumps(item["annotations"]) if item.get("annotations") else None
    row.sql_template = item.get("sql_template") or ""


def _resource_fields(row: McpResourceRow, item: dict) -> None:
    row.uri = item["uri"]
    row.name = item.get("name") or item["uri"]
    row.title = item.get("title")
    row.description = item.get("description")
    row.mime_type = item.get("mime_type")
    row.kind = item.get("kind") or "primary_entity"
    row.content_json = json.dumps(item["content"]) if item.get("content") is not None else None


def _prompt_fields(row: McpPromptRow, item: dict) -> None:
    row.name = item["name"]
    row.title = item.get("title")
    row.description = item.get("description")
    row.arguments_json = json.dumps(item.get("arguments") or [])
    row.template_json = json.dumps(item["template"]) if item.get("template") is not None else None


# --- Helpers ----------------------------------------------------------------

def _active(db: Session, server_id: str) -> dict[str, list]:
    """Load the active (non-soft-deleted) child rows for a server."""
    def q(model):
        return (
            db.query(model)
            .filter(model.server_id == server_id, model.deleted_at.is_(None))
            .order_by(model.created_at, model.id)
            .all()
        )
    return {"tools": q(McpToolRow), "resources": q(McpResourceRow), "prompts": q(McpPromptRow)}


def _meta(rows: list, *fields: str) -> list[dict]:
    """Project active rows to plain dicts for the stage prompts (existing-capability hints)."""
    return [{f: getattr(r, f, None) for f in fields} for r in rows]


def _schema_resource(name: str, schema: dict) -> dict:
    return {
        "uri": f"dataset://{name}/schema",
        "name": "schema",
        "title": "Dataset schema",
        "description": "The dataset's tables and entity relationships (JSONSchema).",
        "kind": "schema",
        "mime_type": "application/json",
        "content": schema,
    }


def _entity_resource(name: str, entity: dict) -> dict:
    return {
        "uri": entity.get("uri") or f"entity://{name}/{entity.get('name')}",
        "name": entity.get("name") or "entity",
        "title": entity.get("title"),
        "description": entity.get("description"),
        "kind": entity.get("kind") or "primary_entity",
        "mime_type": entity.get("mime_type") or "application/json",
        "content": {"entity": entity.get("name"), "kind": entity.get("kind")},
    }


def _validate_tools(server: McpServerRow, tables: list[dict], tools: list[dict]) -> tuple[list[dict], bool]:
    """Drop tools whose zero-param SQL doesn't compile against the dataset (parquet only)."""
    if (server.type or "parquet") != "parquet":
        return tools, False  # external (BETA): trust the generated SQL
    conn = new_connection()
    try:
        for t in tables:
            try:
                register_parquet_view(conn, t["table_name"], t.get("parquet_path"))
            except Exception:
                pass
        kept: list[dict] = []
        dropped = False
        for tool in tools:
            sql = tool.get("sql_template") or ""
            props = ((tool.get("input_schema") or {}).get("properties")) or {}
            if props:
                kept.append(tool)  # can't safely compile-check parameterized SQL — trust it
                continue
            try:
                _run_select_params(conn, f"SELECT * FROM ({sql}) AS _v LIMIT 0", None, 0)
                kept.append(tool)
            except Exception as exc:
                dropped = True
                log.warning("sync.tool_invalid", name=tool.get("name"), error=str(exc))
        return kept, dropped
    finally:
        conn.close()
