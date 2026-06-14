import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from datachat.api.common import api_error, ok
from datachat.config.settings import get_settings
from datachat.db.models import UploadRow
from datachat.db.session import get_session
from datachat.pipeline.csv_reader import read_csv_metadata

router = APIRouter(prefix="/api/uploads")


@router.post("")
def upload_csv(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    if not file.filename or not file.filename.endswith(".csv"):
        raise api_error("invalid_file", "Only CSV files are accepted.")

    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}.csv"
    dest = upload_dir / safe_name
    contents = file.file.read()
    dest.write_bytes(contents)

    try:
        row_count, columns = read_csv_metadata(str(dest))
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise api_error("parse_error", f"Could not parse CSV: {exc}")

    row = UploadRow(
        filename=safe_name,
        original_filename=file.filename,
        row_count=row_count,
        columns_json=json.dumps(columns),
    )
    session.add(row)
    session.flush()

    return ok({
        "id": row.id,
        "original_filename": row.original_filename,
        "row_count": row.row_count,
        "columns": columns,
        "uploaded_at": row.uploaded_at.isoformat(),
    })


@router.get("/{upload_id}")
def get_upload(upload_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(UploadRow, upload_id)
    if row is None:
        raise api_error("not_found", "Upload not found.", status_code=404)
    return ok({
        "id": row.id,
        "original_filename": row.original_filename,
        "row_count": row.row_count,
        "columns": row.columns,
        "uploaded_at": row.uploaded_at.isoformat(),
    })
