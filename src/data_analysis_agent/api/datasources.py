from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from data_analysis_agent.api._common import api_error
from data_analysis_agent.api._repository import get_data_source_or_404
from data_analysis_agent.config.settings import get_settings
from data_analysis_agent.db.models import DataSourceRow, DatasetTableRow, SessionDataSourceRow
from data_analysis_agent.db.session import get_session
from data_analysis_agent.tools.connectors.base import DatasetConnectionError, get_connector
from data_analysis_agent.tools.connectors.uri import DatasetURI
from data_analysis_agent.tools.descriptions import generate_dataset_descriptions
from data_analysis_agent.tools.ingester import FileIngester
from data_analysis_agent.tools.mcp.pool import get_manager
from data_analysis_agent.tools.table_naming import sql_table_name

log = structlog.get_logger()
router = APIRouter()

SUPPORTED_EXTENSIONS = (".csv", ".xlsx", ".xls", ".json")
_EXTERNAL_TYPES = ("postgresql", "postgres")


@router.post("/datasources/upload")
def upload_data_source(
    request: Request,
    dataset_name: Annotated[str, Form()] = "",
    dataset_type: Annotated[str, Form()] = "parquet",
    dataset_uri: Annotated[str, Form()] = "",
    file: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    """Create a Dataset: an internal Parquet dataset (CSV upload) or an external DB (BETA)."""
    name = dataset_name.strip()
    if not name:
        raise api_error("INVALID_NAME", "Dataset name is required.")
    if _name_taken(session, name):
        raise api_error("DUPLICATE_NAME", f"A dataset named '{name}' already exists.")
    dtype = (dataset_type or "parquet").strip().lower()

    if dtype in _EXTERNAL_TYPES:
        return _create_external_dataset(session, name, dataset_uri.strip())

    if file is None or not (file.filename or ""):
        raise api_error("NO_FILE", "Choose a CSV/XLSX/JSON file to upload.")
    _require_supported_extension(file.filename or "")
    ds = DataSourceRow(name=name, type="parquet", uri=f"parquet:///{quote(name, safe='')}")
    session.add(ds)
    session.flush()
    _ingest_table(session, ds.id, file)
    _regenerate_descriptions(session, ds)
    _check_connection_or_400(session, ds)
    log.info("dataset.created", dataset_id=ds.id, name=name, type="parquet")
    return RedirectResponse(url="/", status_code=303)


@router.post("/datasources/{datasource_id}/add-csv")
def add_csv(
    request: Request,
    datasource_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Append a new table (CSV) to an existing Parquet dataset; re-describe; refresh pools."""
    ds = get_data_source_or_404(session, datasource_id)
    if (ds.type or "").lower() in _EXTERNAL_TYPES:
        raise api_error("NOT_PARQUET", "CSVs can only be added to an internal (parquet) dataset.")
    if not (file.filename or ""):
        raise api_error("NO_FILE", "Choose a CSV file to add.")
    _require_supported_extension(file.filename or "")
    _ingest_table(session, ds.id, file)
    _regenerate_descriptions(session, ds)
    _check_connection_or_400(session, ds)
    _close_pools_using(session, datasource_id)  # make the new table visible to live sessions
    log.info("dataset.table_added", dataset_id=ds.id, name=ds.name)
    return RedirectResponse(url="/", status_code=303)


@router.post("/datasources/{datasource_id}/sync")
def sync_data_source(
    request: Request,
    datasource_id: str,
    session: Session = Depends(get_session),
):
    """Re-generate the dataset + per-table descriptions over ALL tables; record any connect error."""
    ds = get_data_source_or_404(session, datasource_id)
    _regenerate_descriptions(session, ds)
    try:
        dataset, tables = _dataset_and_tables(session, ds)
        get_connector(dataset, tables).connection_check()
        ds.connection_error = None
        ds.last_synced_at = datetime.now(timezone.utc)
    except DatasetConnectionError as exc:
        ds.connection_error = str(exc)  # sanitized (display-based); shown as a badge
        log.warning("dataset.sync_connection_error", dataset_id=datasource_id, error=str(exc))
    _close_pools_using(session, datasource_id)
    log.info("dataset.synced", dataset_id=datasource_id, name=ds.name)
    return RedirectResponse(url="/", status_code=303)


@router.post("/datasources/{datasource_id}/delete")
def delete_data_source(
    request: Request,
    datasource_id: str,
    session: Session = Depends(get_session),
):
    """Delete a dataset, its tables + session links, and its whole on-disk directory."""
    ds = get_data_source_or_404(session, datasource_id)
    _close_pools_using(session, datasource_id)
    _unlink_from_sessions(session, datasource_id)
    session.query(DatasetTableRow).filter(DatasetTableRow.dataset_id == datasource_id).delete()
    legacy_parquet = ds.parquet_path  # pre-migration single-file rows
    session.delete(ds)
    _remove_dataset_dir(datasource_id)
    if legacy_parquet:
        Path(legacy_parquet).unlink(missing_ok=True)
    log.info("dataset.deleted", dataset_id=datasource_id)
    return RedirectResponse(url="/", status_code=303)


# --- internals --------------------------------------------------------------

def _create_external_dataset(session: Session, name: str, uri: str) -> RedirectResponse:
    """Create an external (Postgres, BETA) dataset by introspecting the URI. 501 when disabled."""
    if not get_settings().enable_external_datasets:
        raise api_error(
            "EXTERNAL_DISABLED",
            "External database datasets are not enabled (set DATAANALYSIS_ENABLE_EXTERNAL_DATASETS).",
            status_code=501,
        )
    if not uri:
        raise api_error("NO_URI", "Provide a database connection URI.")
    ds = DataSourceRow(name=name, type="postgresql", uri=uri)
    session.add(ds)
    session.flush()
    dataset = {"id": ds.id, "name": name, "type": "postgresql", "uri": ds.dataset_uri}
    try:
        connector = get_connector(dataset, [])
        connector.connection_check()
        discovered = connector.discover_tables()
    except DatasetConnectionError as exc:
        raise api_error("CONNECTION_FAILED", str(exc))
    for t in discovered:
        row = DatasetTableRow(
            dataset_id=ds.id,
            table_name=t["table_name"],
            row_count=t.get("row_count"),
            schema_json=json.dumps(t.get("schema") or []),
        )
        row.column_names = t.get("column_names", [])
        session.add(row)
    session.flush()
    _regenerate_descriptions(session, ds)
    log.info("dataset.created", dataset_id=ds.id, name=name, type="postgresql",
             uri=DatasetURI(uri).display(), tables=len(discovered))
    return RedirectResponse(url="/", status_code=303)


def _ingest_table(session: Session, dataset_id: str, file: UploadFile) -> DatasetTableRow:
    """Stream a CSV straight to ``{datasets_dir}/{dataset_id}/{table}.parquet`` as a new table."""
    filename = file.filename or "data.csv"
    table_name = _unique_table_name(session, dataset_id, filename)
    dataset_dir = Path(get_settings().datasets_dir) / dataset_id
    suffix = Path(filename).suffix.lower()
    try:
        result = FileIngester().ingest_stream(file.file, suffix, dataset_dir, table_name)
    except Exception as exc:
        session.rollback()
        raise api_error("PARSE_FAILED", f"Could not process file: {exc}")
    row = DatasetTableRow(
        dataset_id=dataset_id,
        table_name=table_name,
        source_filename=filename,
        parquet_path=result.parquet_path,
        row_count=result.row_count,
        schema_json=result.schema_json,
    )
    row.column_names = result.column_names
    session.add(row)
    session.flush()
    return row


def _unique_table_name(session: Session, dataset_id: str, filename: str) -> str:
    """Derive a SQL-safe table name from the filename, auto-suffixing on collision in the dataset."""
    base = sql_table_name(filename)
    existing = {
        t.table_name
        for t in session.query(DatasetTableRow).filter(DatasetTableRow.dataset_id == dataset_id).all()
    }
    if base not in existing:
        return base
    i = 2
    while f"{base}_{i}" in existing:
        i += 1
    return f"{base}_{i}"


def _regenerate_descriptions(session: Session, ds: DataSourceRow) -> None:
    """Regenerate the dataset's tool_description + every per-table capability_description."""
    tables = (
        session.query(DatasetTableRow)
        .filter(DatasetTableRow.dataset_id == ds.id)
        .order_by(DatasetTableRow.created_at)
        .all()
    )
    payload = [
        {"table_name": t.table_name, "schema": t.schema, "row_count": t.row_count, "parquet_path": t.parquet_path}
        for t in tables
    ]
    descriptions = generate_dataset_descriptions(ds.name, payload)
    ds.tool_description = descriptions.tool
    for t in tables:
        t.capability_description = descriptions.capabilities.get(t.table_name) or t.capability_description


def _check_connection_or_400(session: Session, ds: DataSourceRow) -> None:
    """Run the dataset connection-check before commit; 400 (credential-free) on failure."""
    dataset, tables = _dataset_and_tables(session, ds)
    try:
        get_connector(dataset, tables).connection_check()
    except DatasetConnectionError as exc:
        raise api_error("CONNECTION_FAILED", str(exc))


def _dataset_and_tables(session: Session, ds: DataSourceRow) -> tuple[dict, list[dict]]:
    """Serialise a dataset row + its tables into the dicts the connectors expect."""
    rows = session.query(DatasetTableRow).filter(DatasetTableRow.dataset_id == ds.id).all()
    dataset = {"id": ds.id, "name": ds.name, "type": ds.type, "uri": ds.dataset_uri,
               "tool_description": ds.tool_description}
    tables = [
        {"table_name": t.table_name, "parquet_path": t.parquet_path,
         "column_names": t.column_names, "row_count": t.row_count,
         "capability_description": t.capability_description}
        for t in rows
    ]
    return dataset, tables


def _name_taken(session: Session, name: str) -> bool:
    """Return True if a dataset with this name already exists (API-level uniqueness)."""
    return session.query(DataSourceRow).filter(DataSourceRow.name == name).first() is not None


def _require_supported_extension(filename: str) -> None:
    """Raise a recoverable API error if the filename has an unsupported extension."""
    if not any(filename.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        raise api_error("INVALID_FILE", f"Supported file types: {', '.join(SUPPORTED_EXTENSIONS)}")


def _remove_dataset_dir(dataset_id: str) -> None:
    """Remove the dataset's on-disk Parquet directory (best-effort)."""
    shutil.rmtree(Path(get_settings().datasets_dir) / dataset_id, ignore_errors=True)


def _close_pools_using(session: Session, datasource_id: str) -> None:
    """Close the MCP pool of every session that includes this dataset (lock-safe)."""
    links = (
        session.query(SessionDataSourceRow)
        .filter(SessionDataSourceRow.data_source_id == datasource_id)
        .all()
    )
    manager = get_manager()
    for link in links:
        manager.close(link.session_id)


def _unlink_from_sessions(session: Session, datasource_id: str) -> None:
    """Remove all session join-table rows referencing a dataset."""
    session.query(SessionDataSourceRow).filter(
        SessionDataSourceRow.data_source_id == datasource_id
    ).delete()
