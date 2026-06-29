"""File upload and profiling endpoints."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from api._common import ok, api_error
from config.settings import get_settings
from db.models import SessionRow, UploadedFileRow
from db.session import get_session
from graph.runner import run_profile

router = APIRouter()


@router.post("/sessions/{session_id}/files")
def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
) -> dict:
    """Upload a CSV or Excel (.xlsx) file, profile it, and return the profile."""
    # Validate session
    session = db.get(SessionRow, session_id)
    if session is None:
        raise api_error("SESSION_NOT_FOUND", "Session not found", status_code=404)

    # Validate file extension (use safe name only — strip any path components)
    raw_name = file.filename or ""
    filename = Path(raw_name).name  # strips ../../ traversal attempts
    if not filename:
        raise api_error("INVALID_FILE", "File has no name")
    if not filename.lower().endswith(".csv") and not filename.lower().endswith(".xlsx"):
        raise api_error("INVALID_FILE", "Only CSV and Excel (.xlsx) files are supported")

    # Enforce file size limit (50 MB)
    _MAX_BYTES = 50 * 1024 * 1024
    content = file.file.read()
    if len(content) > _MAX_BYTES:
        raise api_error("FILE_TOO_LARGE", f"File exceeds the 50 MB limit ({len(content) // (1024*1024)} MB uploaded)")

    # Save to temp dir
    settings = get_settings()
    temp_dir: Path = settings.get_temp_dir() / session_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / filename
    temp_path.write_bytes(content)

    # Profile the file (pure pandas, no LLM)
    file_row = UploadedFileRow(
        session_id=session_id,
        filename=filename,
        temp_path=str(temp_path),
        profile_json="{}",  # placeholder; updated below
    )
    db.add(file_row)
    db.flush()
    file_id = file_row.id

    profile_dict = run_profile(
        session_id=session_id,
        file_id=file_id,
        filename=filename,
        file_path=str(temp_path),
    )

    # Update DB row with real profile JSON
    file_row.profile_json = json.dumps(profile_dict)

    return ok({"file_id": file_id, "filename": filename, "profile": profile_dict})
