import json
import uuid
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import DatasetRow
from domain.dataset import DatasetUploadResponse, DatasetListItem

router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise api_error("FILE_TOO_LARGE", "File exceeds 50 MB limit", 413)

    # Validate it's a valid CSV
    try:
        df = pd.read_csv(BytesIO(content))
    except Exception as e:
        raise api_error("INVALID_CSV", f"Could not parse CSV: {e}", 400)

    # Save to disk
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dataset_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{dataset_id}.csv"
    file_path.write_bytes(content)

    # Persist metadata
    column_names = list(df.columns)
    row = DatasetRow(
        id=dataset_id,
        filename=file.filename or "upload.csv",
        row_count=len(df),
        column_names_json=json.dumps(column_names),
        file_path=str(file_path),
    )
    session.add(row)
    session.flush()

    return ok(
        DatasetUploadResponse(
            dataset_id=dataset_id,
            filename=row.filename,
            row_count=len(df),
            column_names=column_names,
        ).model_dump()
    )


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session)) -> dict:
    rows = session.query(DatasetRow).order_by(DatasetRow.uploaded_at.desc()).all()
    items = [
        DatasetListItem(
            dataset_id=r.id,
            filename=r.filename,
            row_count=r.row_count,
            column_names=json.loads(r.column_names_json) if r.column_names_json else [],
            uploaded_at=r.uploaded_at,
        )
        for r in rows
    ]
    return ok([i.model_dump(mode="json") for i in items])
