import json
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import UploadRow
from domain.analysis import UploadResponse, ColumnInfo

router = APIRouter()

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
_MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
_ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _dtype_name(dtype) -> str:
    """Convert pandas dtype to a readable string."""
    name = str(dtype)
    if name.startswith("int"):
        return "integer"
    if name.startswith("float"):
        return "float"
    if name.startswith("bool"):
        return "boolean"
    if name in ("object", "string", "str"):
        return "string"
    if name.startswith("datetime"):
        return "datetime"
    # pandas uses "object" for generic/string columns — catch any remaining
    if "object" in name:
        return "string"
    return name


@router.post("/uploads")
async def upload_file(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    # Validate extension
    original_name = file.filename or ""
    suffix = Path(original_name).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise api_error(
            "INVALID_FILE_TYPE",
            f"Only CSV and Excel files are accepted. Got: '{suffix or 'no extension'}'",
            400,
        )

    # Read content and check size
    content = await file.read()
    if len(content) > _MAX_SIZE_BYTES:
        raise api_error("FILE_TOO_LARGE", "File exceeds the 50 MB limit.", 400)

    # Parse with pandas
    try:
        import io
        if suffix == ".csv":
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as exc:
        raise api_error("PARSE_ERROR", f"Failed to parse file: {exc}", 400)

    row_count, col_count = df.shape
    columns = [ColumnInfo(name=col, dtype=_dtype_name(df[col].dtype)) for col in df.columns]

    # Persist to disk
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    dest = _UPLOAD_DIR / f"{file_id}{suffix}"
    dest.write_bytes(content)

    # Insert DB row
    upload = UploadRow(
        id=file_id,
        filename=original_name,
        filepath=str(dest),
        row_count=row_count,
        col_count=col_count,
        columns_json=json.dumps([c.model_dump() for c in columns]),
    )
    session.add(upload)
    session.flush()

    return ok(
        UploadResponse(
            upload_id=upload.id,
            filename=upload.filename,
            row_count=upload.row_count,
            col_count=upload.col_count,
            columns=columns,
        ).model_dump()
    )


@router.get("/uploads")
def list_uploads(session: Session = Depends(get_session)) -> dict:
    rows = (
        session.query(UploadRow)
        .order_by(UploadRow.uploaded_at.desc())
        .all()
    )
    result = []
    for row in rows:
        columns = json.loads(row.columns_json)
        result.append(
            UploadResponse(
                upload_id=row.id,
                filename=row.filename,
                row_count=row.row_count,
                col_count=row.col_count,
                columns=[ColumnInfo(**c) for c in columns],
                uploaded_at=row.uploaded_at.isoformat() if row.uploaded_at else None,
            ).model_dump()
        )
    return ok(result)
