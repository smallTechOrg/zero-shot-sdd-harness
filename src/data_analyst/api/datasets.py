import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from data_analyst.api._common import api_error
from data_analyst.db.models import AuditLogEntryRow, DatasetRow, SessionRow
from data_analyst.db.session import get_session
from data_analyst.observability import get_logger
from data_analyst.tools import duck

router = APIRouter()
log = get_logger("data_analyst.datasets")

_SUFFIX_FORMAT = {".csv": "csv", ".parquet": "parquet"}


@router.post("/sessions/{session_id}/datasets")
async def upload_dataset(
    session_id: int,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    db: Session = Depends(get_session),
) -> dict:
    if db.get(SessionRow, session_id) is None:
        raise api_error("session_not_found", "Session not found.", 404)

    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    file_format = _SUFFIX_FORMAT.get(suffix)
    if file_format is None:
        raise api_error("unsupported_format", "Only .csv and .parquet are supported.", 400)

    display_name = (name or Path(filename).stem).strip() or "dataset"
    table = duck.sanitize_table_name(f"s{session_id}_{display_name}")
    started = time.perf_counter()

    tmp_path = None
    try:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        row_count, schema = duck.ingest_file(tmp_path, table, file_format)
        sample_rows = duck.get_sample_rows(table, _sample_limit())

        dataset = DatasetRow(
            session_id=session_id,
            name=display_name,
            source_filename=filename,
            file_format=file_format,
            duckdb_table=table,
            row_count=row_count,
            schema_json=[c.model_dump() for c in schema],
            sample_rows_json=sample_rows,
        )
        db.add(dataset)
        db.add(
            AuditLogEntryRow(
                session_id=session_id,
                nl_prompt=f"[ingest] {filename}",
                generated_sql=None,
                row_count=row_count,
                duration_ms=int((time.perf_counter() - started) * 1000),
                status="success",
            )
        )
        db.flush()
        return {
            "id": dataset.id,
            "session_id": session_id,
            "name": display_name,
            "file_format": file_format,
            "duckdb_table": table,
            "row_count": row_count,
            "schema": dataset.schema_json,
        }
    except Exception as exc:  # noqa: BLE001
        log.error("dataset.ingest_failed", error=str(exc), filename=filename)
        db.rollback()
        _audit_failure(session_id, filename, started, str(exc))
        raise api_error("ingest_failed", f"Could not ingest file: {exc}", 500)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@router.get("/sessions/{session_id}/datasets")
def list_datasets(session_id: int, db: Session = Depends(get_session)) -> dict:
    if db.get(SessionRow, session_id) is None:
        raise api_error("session_not_found", "Session not found.", 404)
    rows = (
        db.query(DatasetRow)
        .filter(DatasetRow.session_id == session_id)
        .order_by(DatasetRow.created_at.desc())
        .all()
    )
    return {
        "datasets": [
            {
                "id": r.id,
                "name": r.name,
                "row_count": r.row_count,
                "file_format": r.file_format,
                "duckdb_table": r.duckdb_table,
            }
            for r in rows
        ]
    }


def _sample_limit() -> int:
    from data_analyst.config.settings import get_settings

    return get_settings().sample_rows


def _audit_failure(session_id: int, filename: str, started: float, error: str) -> None:
    from data_analyst.db.session import create_db_session

    try:
        with create_db_session() as session:
            session.add(
                AuditLogEntryRow(
                    session_id=session_id,
                    nl_prompt=f"[ingest] {filename}",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    status="error",
                    error_message=error,
                )
            )
    except Exception as exc:  # noqa: BLE001
        log.error("audit.write_failed", error=str(exc))
