import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import SessionRow

from data.ingest import ingest_file

router = APIRouter()


@router.post("/datasets")
async def create_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    filename = file.filename or "upload.csv"
    file_bytes = await file.read()
    if not file_bytes:
        raise api_error("BAD_REQUEST", "Uploaded file is empty.", 400)

    # Resolve or create the session.
    if session_id:
        existing = session.get(SessionRow, session_id)
        if existing is None:
            raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)
        resolved_id = existing.id
    else:
        new_session = SessionRow(title=filename)
        session.add(new_session)
        session.flush()
        resolved_id = new_session.id
        session.commit()

    try:
        info = ingest_file(file_bytes, filename, resolved_id)
    except ValueError as exc:
        raise api_error("BAD_REQUEST", str(exc), 400)
    except Exception as exc:
        raise api_error("INTERNAL", f"Ingestion failed: {exc}", 500)

    return ok(
        {
            "session_id": resolved_id,
            "dataset_id": info["dataset_id"],
            "table_name": info["table_name"],
            "row_count": info["row_count"],
            "columns": info["columns"],
        }
    )
