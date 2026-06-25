from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import pyarrow.parquet as pq
import structlog
from fastapi import APIRouter, Body, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from data_analysis_agent.api import templates
from data_analysis_agent.api._common import api_error, render
from data_analysis_agent.api._repository import get_mcp_server_or_404
from data_analysis_agent.config.settings import get_settings
from data_analysis_agent.db.models import (
    McpPromptRow,
    McpResourceRow,
    McpServerRow,
    McpToolRow,
    SessionMcpServerRow,
)
from data_analysis_agent.db.session import get_session
from data_analysis_agent.tools.connectors.base import DatasetConnectionError, get_connector
from data_analysis_agent.tools.connectors.uri import DatasetURI
from data_analysis_agent.tools.ingester import FileIngester
from data_analysis_agent.tools.mcp.dispatch import handle_jsonrpc
from data_analysis_agent.tools.mcp.pool import get_manager
from data_analysis_agent.tools.sync import apply_sync_result, run_sync
from data_analysis_agent.tools.table_naming import sql_table_name

log = structlog.get_logger()
router = APIRouter()

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls", ".json")
_EXTERNAL_TYPES = ("postgresql", "postgres")


# --- Upload (auxiliary): CSV → Parquet, returns the data URI ----------------

@router.post("/mcpserver/upload")
def upload_csv(
    dataset_name: Annotated[str, Form()] = "",
    file: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    """Convert a CSV to Parquet under the named dataset directory; return its data URI. No entity."""
    name = dataset_name.strip()
    if not name:
        raise api_error("INVALID_NAME", "Dataset name is required.")
    if file is None or not (file.filename or ""):
        raise api_error("NO_FILE", "Choose a CSV/XLSX/JSON file to upload.")
    _require_supported_extension(file.filename or "")
    directory = _dataset_dir(name)
    table = _unique_table_name(directory, file.filename or "data.csv")
    suffix = Path(file.filename or "").suffix.lower()
    try:
        FileIngester().ingest_stream(file.file, suffix, directory, table)
    except Exception as exc:
        raise api_error("PARSE_FAILED", f"Could not process file: {exc}")
    log.info("mcpserver.upload", dataset=name, table=table)
    return JSONResponse({"uri": _parquet_uri(name), "table": table})


# --- Create: build the server from a URI + run sync -------------------------

@router.post("/mcpserver")
def create_server(
    dataset_uri: Annotated[str, Form()] = "",
    dataset_type: Annotated[str, Form()] = "parquet",
    name: Annotated[str, Form()] = "",
    session: Session = Depends(get_session),
):
    """Create an MCP server from a dataset URI (1:1), connection-check it, then run the sync pipeline."""
    uri = dataset_uri.strip()
    dtype = (dataset_type or "parquet").strip().lower()
    if dtype in _EXTERNAL_TYPES:
        return _create_external(session, name.strip(), uri)
    return _create_parquet(session, name.strip(), uri)


def _create_parquet(session: Session, name: str, uri: str) -> RedirectResponse:
    nm = name or DatasetURI(uri).database
    if not nm:
        raise api_error("INVALID_NAME", "Dataset name is required.")
    _reject_duplicates(session, nm, _parquet_uri(nm))
    tables = _introspect_parquet_dir(_dataset_dir(nm))
    if not tables:
        raise api_error("NO_DATA", "No uploaded data found for this dataset. Upload a CSV first.")
    server = McpServerRow(name=nm, type="parquet", uri=_parquet_uri(nm))
    session.add(server)
    session.flush()
    server.physical_tables = tables
    _connection_check_or_400(server)
    _generate(session, server)
    log.info("mcpserver.created", server_id=server.id, name=nm, type="parquet", tables=len(tables))
    return RedirectResponse(url="/", status_code=303)


def _create_external(session: Session, name: str, uri: str) -> RedirectResponse:
    if not get_settings().enable_external_datasets:
        raise api_error(
            "EXTERNAL_DISABLED",
            "External database datasets are not enabled (set DATAANALYSIS_ENABLE_EXTERNAL_DATASETS).",
            status_code=501,
        )
    if not uri:
        raise api_error("NO_URI", "Provide a database connection URI.")
    nm = name or DatasetURI(uri).database
    if not nm:
        raise api_error("INVALID_NAME", "Dataset name is required.")
    _reject_duplicates(session, nm, uri)
    server = McpServerRow(name=nm, type="postgresql", uri=uri)
    session.add(server)
    session.flush()
    try:
        connector = get_connector(_server_dict(server), [])
        connector.connection_check()
        server.physical_tables = connector.discover_tables()
    except DatasetConnectionError as exc:
        raise api_error("CONNECTION_FAILED", str(exc))
    _generate(session, server)
    log.info("mcpserver.created", server_id=server.id, name=nm, type="postgresql",
             uri=DatasetURI(uri).display(), tables=len(server.physical_tables))
    return RedirectResponse(url="/", status_code=303)


# --- Sync: regenerate capabilities (versioned, soft-delete) -----------------

@router.post("/mcpserver/{server_id}/sync")
def sync_server(server_id: str, session: Session = Depends(get_session)):
    """Re-run the 5-stage pipeline, apply incrementally (version++, soft-delete), refresh pools."""
    server = get_mcp_server_or_404(session, server_id)
    _connection_check_or_400(server)
    server.connection_error = None
    _generate(session, server)
    get_manager().close_sessions_for_server(server_id)
    log.info("mcpserver.synced", server_id=server_id, name=server.name, version=server.version)
    return RedirectResponse(url="/", status_code=303)


@router.post("/mcpserver/{server_id}/add-csv")
def add_csv(
    server_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Append a CSV as a new table to an internal server, re-introspect, and re-sync (Phase A)."""
    server = get_mcp_server_or_404(session, server_id)
    if (server.type or "").lower() != "parquet":
        raise api_error("NOT_PARQUET", "CSVs can only be added to an internal (parquet) server.")
    if not (file.filename or ""):
        raise api_error("NO_FILE", "Choose a CSV file to add.")
    _require_supported_extension(file.filename or "")
    directory = _dataset_dir(server.name)
    table = _unique_table_name(directory, file.filename or "data.csv")
    suffix = Path(file.filename or "").suffix.lower()
    try:
        FileIngester().ingest_stream(file.file, suffix, directory, table)
    except Exception as exc:
        raise api_error("PARSE_FAILED", f"Could not process file: {exc}")
    server.physical_tables = _introspect_parquet_dir(directory)
    _connection_check_or_400(server)
    _generate(session, server)
    get_manager().close_sessions_for_server(server_id)
    log.info("mcpserver.table_added", server_id=server_id, table=table)
    return RedirectResponse(url="/", status_code=303)


# --- MCP JSON-RPC dispatch --------------------------------------------------

@router.post("/mcpserver/{server_id}")
def mcp_dispatch(
    server_id: str,
    payload: Annotated[dict, Body(...)],
    session: Session = Depends(get_session),
):
    """Single MCP JSON-RPC 2.0 endpoint over the server's stored tools/resources/prompts."""
    server = get_mcp_server_or_404(session, server_id)
    return JSONResponse(handle_jsonrpc(session, server, payload))


# --- Detail + delete --------------------------------------------------------

@router.get("/mcpserver/{server_id}")
def server_detail(request: Request, server_id: str, session: Session = Depends(get_session)):
    """Render an MCP server's detail page: metadata + active tools/resources/prompts."""
    server = get_mcp_server_or_404(session, server_id)
    return render(request, templates, "mcpserver.html", server=_detail_view(session, server))


@router.post("/mcpserver/{server_id}/delete")
def delete_server(server_id: str, session: Session = Depends(get_session)):
    """Delete a server, its capability rows + session links, and its on-disk directory."""
    server = get_mcp_server_or_404(session, server_id)
    get_manager().close_sessions_for_server(server_id)
    session.query(SessionMcpServerRow).filter(
        SessionMcpServerRow.mcp_server_id == server_id
    ).delete()
    for model in (McpToolRow, McpResourceRow, McpPromptRow):
        session.query(model).filter(model.server_id == server_id).delete()
    name = server.name
    session.delete(server)
    shutil.rmtree(_dataset_dir(name), ignore_errors=True)
    log.info("mcpserver.deleted", server_id=server_id)
    return RedirectResponse(url="/", status_code=303)


# --- internals --------------------------------------------------------------

def _generate(session: Session, server: McpServerRow) -> None:
    """Run the sync pipeline and apply it transactionally (caller's session commits)."""
    result = run_sync(session, server)
    apply_sync_result(session, server, result)


def _connection_check_or_400(server: McpServerRow) -> None:
    """Run the server's connection-check; 400 (credential-free) on failure."""
    try:
        get_connector(_server_dict(server), server.physical_tables).connection_check()
    except DatasetConnectionError as exc:
        raise api_error("CONNECTION_FAILED", str(exc))


def _introspect_parquet_dir(directory: Path) -> list[dict]:
    """Build the physical-table catalog from the Parquet files in a dataset directory."""
    tables: list[dict] = []
    for path in sorted(directory.glob("*.parquet")):
        pf = pq.ParquetFile(str(path))
        schema = pf.schema_arrow
        tables.append({
            "table_name": path.stem,
            "parquet_path": str(path.resolve()),
            "source_filename": None,
            "column_names": list(schema.names),
            "schema": [{"name": f.name, "dtype": str(f.type), "nullable": f.nullable} for f in schema],
            "row_count": pf.metadata.num_rows,
        })
    return tables


def _unique_table_name(directory: Path, filename: str) -> str:
    """SQL-safe table name from a filename, auto-suffixed on collision within the directory."""
    base = sql_table_name(filename)
    existing = {p.stem for p in directory.glob("*.parquet")} if directory.exists() else set()
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def _detail_view(db: Session, server: McpServerRow) -> dict:
    """Credential-free detail view-model with the active capability rows."""
    def active(model):
        return (
            db.query(model)
            .filter(model.server_id == server.id, model.deleted_at.is_(None))
            .order_by(model.created_at, model.id)
            .all()
        )
    return {
        "id": server.id,
        "name": server.name,
        "title": server.title,
        "description": server.description,
        "type": server.type,
        "uri_display": DatasetURI(server.uri).display(),
        "version": server.version,
        "last_sync_status": server.last_sync_status,
        "last_synced_at": server.last_synced_at,
        "connection_error": server.connection_error,
        "tables": server.physical_tables,
        "tools": active(McpToolRow),
        "resources": active(McpResourceRow),
        "prompts": active(McpPromptRow),
    }


def _reject_duplicates(session: Session, name: str, uri: str) -> None:
    """Enforce 1:1 dataset↔server: reject a duplicate name or URI (API-level, before flush)."""
    if session.query(McpServerRow).filter(McpServerRow.name == name).first():
        raise api_error("DUPLICATE_NAME", f"An MCP server named '{name}' already exists.")
    if session.query(McpServerRow).filter(McpServerRow.uri == uri).first():
        raise api_error("DUPLICATE_URI", "An MCP server already exists for this dataset URI.")


def _require_supported_extension(filename: str) -> None:
    if not any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise api_error("INVALID_FILE", f"Supported file types: {', '.join(SUPPORTED_EXTENSIONS)}")


def _server_dict(server: McpServerRow) -> dict:
    return {"id": server.id, "name": server.name, "type": server.type, "uri": server.uri}


def _dataset_dir(name: str) -> Path:
    """The on-disk directory for a dataset's Parquet files: ``{datasets_dir}/{slug(name)}``."""
    return Path(get_settings().datasets_dir) / sql_table_name(name)


def _parquet_uri(name: str) -> str:
    from urllib.parse import quote
    return f"parquet:///{quote(name, safe='')}"
