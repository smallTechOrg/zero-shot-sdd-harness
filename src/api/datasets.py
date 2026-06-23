import json

from fastapi import APIRouter, Depends, UploadFile, File, Header
from sqlalchemy.orm import Session
from sqlalchemy import select

from api._common import ok, api_error
from db.session import get_session
from db.models import SessionRow, DatasetRow

router = APIRouter()


def upsert_session(session_id: str, db_session: Session) -> SessionRow:
    """Upsert SessionRow by session_id — update last_seen_at if exists, insert if not."""
    from datetime import datetime, timezone

    row = db_session.get(SessionRow, session_id)
    if row is None:
        row = SessionRow(id=session_id)
        db_session.add(row)
    else:
        row.last_seen_at = datetime.now(timezone.utc)
    db_session.flush()
    return row


@router.post("/datasets/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    x_session_id: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    if not x_session_id:
        raise api_error("MISSING_SESSION", "X-Session-ID header is required", 400)

    # Upsert session (within the open ORM session)
    upsert_session(x_session_id, session)

    # Parse the uploaded file (pure in-memory, no DB writes yet)
    from ingest.parser import parse_upload
    df = await parse_upload(file)

    filename = file.filename or "upload.csv"

    # Commit + close the ORM session BEFORE loading to SQLite.
    # This releases the write lock so load_dataset can acquire it.
    session.commit()

    # Load into SQLite table — returns a plain dict (detachment-safe)
    from ingest.loader import load_dataset
    dataset_data = load_dataset(x_session_id, filename, df)

    columns = json.loads(dataset_data["column_names"])

    return ok({
        "dataset_id": dataset_data["id"],
        "session_id": dataset_data["session_id"],
        "table_name": dataset_data["table_name"],
        "original_filename": dataset_data["original_filename"],
        "row_count": dataset_data["row_count"],
        "column_names": columns,
        "created_at": dataset_data["created_at"].isoformat(),
    })


@router.get("/datasets")
def list_datasets(
    x_session_id: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> dict:
    if not x_session_id:
        raise api_error("MISSING_SESSION", "X-Session-ID header is required", 400)

    rows = session.scalars(
        select(DatasetRow).where(DatasetRow.session_id == x_session_id)
    ).all()

    result = []
    for ds in rows:
        try:
            columns = json.loads(ds.column_names)
        except Exception:
            columns = []
        result.append({
            "dataset_id": ds.id,
            "session_id": ds.session_id,
            "table_name": ds.table_name,
            "original_filename": ds.original_filename,
            "row_count": ds.row_count,
            "column_names": columns,
            "created_at": ds.created_at.isoformat(),
        })

    return ok(result)
