import io
import json

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from datachat.api._common import ok, api_error
from datachat.config.settings import get_settings
from datachat.db.models import SessionRow
from datachat.db.session import get_session

router = APIRouter(prefix="/api")


@router.post("/sessions")
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    settings = get_settings()
    content = file.file.read()
    if len(content) > settings.max_upload_bytes:
        raise api_error("FILE_TOO_LARGE", f"File exceeds {settings.max_upload_bytes} bytes", 413)

    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        if ext == "csv":
            df = pd.read_csv(io.BytesIO(content))
        elif ext in ("xls", "xlsx"):
            df = pd.read_excel(io.BytesIO(content))
        elif ext == "json":
            df = pd.read_json(io.BytesIO(content))
        else:
            raise api_error("UNSUPPORTED_TYPE", f"Unsupported file type: .{ext}")
    except Exception as exc:
        if isinstance(exc, Exception) and hasattr(exc, "status_code"):
            raise
        raise api_error("PARSE_ERROR", f"Could not parse file: {exc}", 422)

    row = SessionRow(
        filename=filename,
        status="ready",
        row_count=len(df),
        column_names=json.dumps(list(df.columns)),
    )
    db.add(row)
    db.flush()
    db.refresh(row)

    # Store DataFrame for the agent
    from datachat.graph.nodes import _dataframe_store
    _dataframe_store[row.id] = df

    return ok({
        "session_id": row.id,
        "filename": row.filename,
        "status": row.status,
        "row_count": row.row_count,
        "column_names": row.column_names_list(),
    })


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, db: Session = Depends(get_session)):
    row = db.get(SessionRow, session_id)
    if not row:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)
    return ok({
        "session_id": row.id,
        "filename": row.filename,
        "status": row.status,
        "row_count": row.row_count,
        "column_names": row.column_names_list(),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    })
