"""Sync orchestration.

- Full sync (`run_sync` + `apply_sync_result`): regenerate all 5 stages and **soft-delete** dropped
  capabilities (the only pruning operation).
- Partial sync (`apply_partial` + the six `add_*`/`update_*` ops): apply ONE client-supplied capability,
  then run an **ADDITIVE** cascade of the downstream stages — insert/update only, never soft-delete a
  sibling. One transaction, one version bump.
"""
from __future__ import annotations

import json
import re
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
    RecoverableQueryError,
    _guard_select,
    _run_select_params,
    new_connection,
    register_parquet_view,
)
from data_analysis_agent.tools.sync import stages

log = structlog.get_logger()

_PARAM = re.compile(r"\$(\w+)")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ValidationError(Exception):
    """A client-supplied capability definition is invalid (surfaced as JSON-RPC -32602)."""


@dataclass
class SyncResult:
    """The capabilities a full sync run proposes for a server."""

    title: str
    description: str
    dataset_schema: dict
    resources: list[dict]
    tools: list[dict]
    prompts: list[dict]
    status: str  # "ok" | "partial"


@dataclass
class CascadeFlags:
    """Which downstream stages a mutation must regenerate (additively), in dependency order."""

    tools: bool = False
    prompts: bool = False


@dataclass
class PartialResult:
    """Outcome of a single granular mutation + its additive cascade."""

    child: str
    op: str
    key: str
    tools_changed: bool
    prompts_changed: bool
    status: str


# --- Full sync (run + apply) ------------------------------------------------

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


def apply_sync_result(db: Session, server: McpServerRow, result: SyncResult) -> None:
    """Apply a full :class:`SyncResult`: insert/update/soft-delete children + bump version once."""
    new_version = (server.version or 1) + 1
    _apply_all(db, server, new_version, result)
    server.version = new_version
    server.title = result.title
    server.description = result.description
    server.dataset_schema = result.dataset_schema
    server.last_synced_at = _now()
    server.last_sync_status = result.status


def _apply_all(db: Session, server: McpServerRow, new_version: int, result: SyncResult) -> None:
    """Diff-apply all three child types at ``new_version`` (delete-absent = full-sync semantics)."""
    active = _active(db, server.id)
    _apply(db, server.id, new_version, result.tools, active["tools"], "name", _tool_fields)
    _apply(db, server.id, new_version, result.resources, active["resources"], "uri", _resource_fields)
    _apply(db, server.id, new_version, result.prompts, active["prompts"], "name", _prompt_fields)


# --- Partial sync (granular mutation + additive cascade) --------------------

_CHILD = {
    "tool": (McpToolRow, "name"),
    "resource": (McpResourceRow, "uri"),
    "prompt": (McpPromptRow, "name"),
}
_SETTERS = {}  # populated after the field setters are defined (see bottom)


def add_tool(db, server, definition):
    return apply_partial(db, server, child="tool", op="add", definition=definition,
                         cascade=CascadeFlags(prompts=True))


def update_tool(db, server, definition):
    return apply_partial(db, server, child="tool", op="update", definition=definition,
                         cascade=CascadeFlags(prompts=True))


def add_prompt(db, server, definition):
    return apply_partial(db, server, child="prompt", op="add", definition=definition,
                         cascade=CascadeFlags())


def update_prompt(db, server, definition):
    return apply_partial(db, server, child="prompt", op="update", definition=definition,
                         cascade=CascadeFlags())


def add_resource(db, server, definition):
    return apply_partial(db, server, child="resource", op="add", definition=definition,
                         cascade=CascadeFlags(tools=True, prompts=True))


def update_resource(db, server, definition):
    return apply_partial(db, server, child="resource", op="update", definition=definition,
                         cascade=CascadeFlags(tools=True, prompts=True))


def apply_partial(db: Session, server: McpServerRow, *, child: str, op: str,
                  definition: dict, cascade: CascadeFlags) -> PartialResult:
    """Apply ONE explicit mutation + its additive cascade at one new version, in the caller's txn."""
    new_version = (server.version or 1) + 1
    key_val = _apply_one(db, server, new_version, child, op, definition)
    tools_changed = prompts_changed = False
    status = "ok"
    if cascade.tools:
        tools_changed, dropped = _cascade_tools(db, server, new_version)
        if dropped:
            status = "partial"
    if cascade.prompts:
        prompts_changed = _cascade_prompts(db, server, new_version)
    server.version = new_version
    server.last_synced_at = _now()
    server.last_sync_status = status
    log.info("sync.partial", server=server.name, child=child, op=op, key=key_val, version=new_version,
             status=status)
    return PartialResult(child, op, key_val, tools_changed, prompts_changed, status)


def _apply_one(db: Session, server: McpServerRow, new_version: int, child: str, op: str,
               definition: dict) -> str:
    """Insert-or-update exactly ONE child row at ``new_version``. Validates before mutating."""
    if child not in _CHILD:
        raise ValidationError(f"unknown capability type: {child!r}")
    model, key = _CHILD[child]
    set_fields = _SETTERS[child]
    key_val = definition.get(key)
    if not key_val:
        raise ValidationError(f"missing '{key}'")
    if child == "tool":
        _validate_tool_definition(server, definition)
    existing = _active_one(db, model, server.id, key, key_val)
    if op == "add":
        if existing is not None:
            raise ValidationError(f"{child} '{key_val}' already exists; use {child}s/update")
        row = model()
        row.server_id = server.id
        row.created_version = new_version
        set_fields(row, definition)
        db.add(row)
    elif op == "update":
        if existing is None:
            raise ValidationError(f"unknown {child} '{key_val}'")
        set_fields(existing, definition)
    else:
        raise ValidationError(f"unknown op: {op!r}")
    db.flush()
    return key_val


def _cascade_tools(db: Session, server: McpServerRow, new_version: int) -> tuple[bool, bool]:
    """Regenerate tools from current active entities + physical tables; ADDITIVE apply."""
    active = _active(db, server.id)
    entities = [{"name": r.name, "kind": r.kind} for r in active["resources"]
                if r.kind in ("primary_entity", "secondary_entity")]
    tables = server.physical_tables
    proposed = stages.stage_tools(server.name, entities, tables, _meta(active["tools"], "name"))
    proposed, dropped = _validate_tools(server, tables, proposed)
    _apply(db, server.id, new_version, proposed, active["tools"], "name", _tool_fields, delete_absent=False)
    db.flush()
    return bool(proposed), dropped


def _cascade_prompts(db: Session, server: McpServerRow, new_version: int) -> bool:
    """Regenerate prompts from current active tools; ADDITIVE apply."""
    active = _active(db, server.id)
    proposed = stages.stage_prompts(server.name, _meta(active["tools"], "name"),
                                    _meta(active["prompts"], "name"))
    _apply(db, server.id, new_version, proposed, active["prompts"], "name", _prompt_fields,
           delete_absent=False)
    db.flush()
    return bool(proposed)


def _validate_tool_definition(server: McpServerRow, definition: dict) -> None:
    """Reject a non-SELECT / multi-statement / forbidden / undeclared-param tool at write time."""
    sql = (definition.get("sql_template") or "").strip()
    if not sql:
        raise ValidationError("tool 'sql_template' is required")
    try:
        _guard_select(sql)
    except RecoverableQueryError as exc:
        raise ValidationError(f"sql_template rejected: {exc}")
    used = set(_PARAM.findall(sql))
    declared = set(((definition.get("input_schema") or {}).get("properties") or {}).keys())
    missing = used - declared
    if missing:
        raise ValidationError(f"sql_template uses undeclared param(s): {', '.join(sorted(missing))}")
    if not used and (server.type or "parquet") == "parquet":
        conn = new_connection()
        try:
            for t in server.physical_tables:
                try:
                    register_parquet_view(conn, t["table_name"], t.get("parquet_path"))
                except Exception:
                    pass
            try:
                _run_select_params(conn, f"SELECT * FROM ({sql}) AS _v LIMIT 0", None, 0)
            except Exception as exc:
                raise ValidationError(f"sql_template does not compile: {exc}")
        finally:
            conn.close()


# --- Generic diff/merge apply -----------------------------------------------

def _apply(db, server_id, new_version, proposed, active_rows, key, set_fields, delete_absent=True):
    """Insert new / update matched. If ``delete_absent`` (full sync), soft-delete rows not proposed."""
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
    if delete_absent:
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


_SETTERS.update({"tool": _tool_fields, "resource": _resource_fields, "prompt": _prompt_fields})


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


def _active_one(db, model, server_id, key, key_val):
    return (
        db.query(model)
        .filter(model.server_id == server_id, model.deleted_at.is_(None), getattr(model, key) == key_val)
        .first()
    )


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
