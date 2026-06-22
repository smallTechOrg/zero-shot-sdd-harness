import re
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from data_analyst.api._common import api_error, ok
from data_analyst.audit.logger import AuditLogger
from data_analyst.config.settings import get_settings
from data_analyst.db.models import SessionRow, DatasetRow
from data_analyst.db.session import get_session
from data_analyst.domain.dataset import DatasetResponse
from data_analyst.duckdb_engine import engine as duckdb_engine

router = APIRouter()

_MAX_BYTES = 100 * 1024 * 1024  # 100 MB
_ALLOWED = {"csv", "json", "parquet"}


def _safe_table_name(filename: str, session_id: str, db: Session) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_]", "_", Path(filename).stem)
    if stem and stem[0].isdigit():
        stem = "t_" + stem
    if not stem:
        stem = "table_data"
    # Ensure uniqueness within session
    base = stem
    counter = 0
    while db.query(DatasetRow).filter_by(table_name=stem).first():
        counter += 1
        stem = f"{base}_{counter}"
    return stem


@router.post("/sessions/{session_id}/upload", status_code=201)
async def upload_dataset(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> dict:
    settings = get_settings()

    # Validate session exists
    session_row = db.get(SessionRow, session_id)
    if session_row is None:
        raise api_error("session_not_found", f"Session {session_id} not found", 404)

    # Validate extension
    filename = Path(file.filename).name if file.filename else "upload"
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in _ALLOWED:
        raise api_error(
            "unsupported_format",
            f"File format '{ext}' not supported. Allowed: {', '.join(_ALLOWED)}",
            415,
        )

    # Read and size-check
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise api_error(
            "file_too_large",
            f"File size {len(data)} bytes exceeds limit of {_MAX_BYTES} bytes (100 MB)",
            413,
        )

    # Save file to disk
    upload_dir = settings.resolved_data_dir / "uploads" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file_path.write_bytes(data)

    # Derive safe table name
    table_name = _safe_table_name(filename, session_id, db)

    # Register with DuckDB
    try:
        row_count = duckdb_engine.register_dataset(
            session_id=session_id,
            table_name=table_name,
            file_path=str(file_path),
            file_format=ext,
        )
    except Exception as exc:
        raise api_error("duckdb_error", f"Could not register dataset: {exc}", 422)

    # Persist DatasetRow
    ds_row = DatasetRow(
        session_id=session_id,
        original_filename=filename,
        table_name=table_name,
        file_path=str(file_path),
        file_format=ext,
        row_count=row_count,
    )
    db.add(ds_row)
    db.flush()

    # Audit log
    audit = AuditLogger(settings.resolved_data_dir)
    audit.log(
        event_type="file_upload",
        session_id=session_id,
        payload={
            "filename": filename,
            "table_name": table_name,
            "row_count": row_count,
            "file_size_bytes": len(data),
        },
    )

    return ok(DatasetResponse(
        dataset_id=ds_row.id,
        session_id=ds_row.session_id,
        original_filename=ds_row.original_filename,
        table_name=ds_row.table_name,
        file_format=ds_row.file_format,
        row_count=ds_row.row_count,
        registered_at=ds_row.registered_at,
    ).model_dump())
