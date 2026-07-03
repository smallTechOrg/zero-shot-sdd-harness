"""Dataset endpoints: upload + profile, list, fetch one."""
from __future__ import annotations

import json
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import DatasetRow
from domain.dataset import DatasetOut, DatasetProfile, DatasetSummary
from analysis.loader import detect_format, load_dataframe
from analysis.profiler import profile
from config.settings import get_settings
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.datasets")

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # ~100 MB


def _dataset_out(ds: DatasetRow) -> dict:
    profile_dict = json.loads(ds.profile_json) if ds.profile_json else {}
    return DatasetOut(
        id=ds.id,
        name=ds.name,
        row_count=ds.row_count,
        column_count=ds.column_count,
        file_format=ds.file_format,
        profile=DatasetProfile(**profile_dict),
    ).model_dump()


@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    filename = file.filename or ""

    # Validate extension → file_format (400 on unsupported/missing).
    try:
        file_format = detect_format(filename)
    except ValueError as exc:
        raise api_error("UNSUPPORTED_FILE", str(exc), 400)

    contents = await file.read()
    size_bytes = len(contents)
    if size_bytes == 0:
        raise api_error("EMPTY_FILE", "Uploaded file is empty.", 400)
    if size_bytes > MAX_UPLOAD_BYTES:
        raise api_error(
            "FILE_TOO_LARGE",
            f"File is {size_bytes} bytes; limit is {MAX_UPLOAD_BYTES} bytes (~100 MB).",
            400,
        )

    # Store the file under data/datasets/<uuid>.<ext>.
    ds_id = str(uuid4())
    datasets_dir = get_settings().datasets_dir()
    try:
        datasets_dir.mkdir(parents=True, exist_ok=True)
        stored_path = datasets_dir / f"{ds_id}.{file_format}"
        stored_path.write_bytes(contents)
    except Exception as exc:  # noqa: BLE001
        _log.error("upload.storage_failed", error=str(exc))
        raise api_error("STORAGE_FAILED", f"Could not store the uploaded file: {exc}", 500)

    # Load + profile. A parse failure is a bad-file (400); anything else is 500.
    try:
        df = load_dataframe(str(stored_path), file_format)
    except ValueError as exc:
        try:
            stored_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
        raise api_error("UNPARSEABLE_FILE", f"Could not read the file: {exc}", 400)
    except Exception as exc:  # noqa: BLE001
        _log.error("upload.load_failed", error=str(exc))
        raise api_error("PROFILING_FAILED", f"Failed to read the file: {exc}", 500)

    try:
        profile_dict = profile(df)
    except Exception as exc:  # noqa: BLE001
        _log.error("upload.profile_failed", error=str(exc))
        raise api_error("PROFILING_FAILED", f"Failed to profile the file: {exc}", 500)

    name = os.path.splitext(os.path.basename(filename))[0] or ds_id
    ds = DatasetRow(
        id=ds_id,
        name=name,
        original_filename=filename,
        file_path=str(stored_path),
        file_format=file_format,
        size_bytes=size_bytes,
        row_count=int(df.shape[0]),
        column_count=int(df.shape[1]),
        profile_json=json.dumps(profile_dict, default=str),
    )
    session.add(ds)
    session.flush()

    _log.info("upload.ok", dataset_id=ds.id, rows=ds.row_count, cols=ds.column_count)
    return ok(_dataset_out(ds))


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session)) -> dict:
    rows = session.execute(
        select(DatasetRow).order_by(DatasetRow.created_at.desc())
    ).scalars().all()
    summaries = [
        DatasetSummary(
            id=r.id,
            name=r.name,
            row_count=r.row_count,
            column_count=r.column_count,
            created_at=r.created_at,
        ).model_dump()
        for r in rows
    ]
    return ok(summaries)


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, session: Session = Depends(get_session)) -> dict:
    ds = session.get(DatasetRow, dataset_id)
    if ds is None:
        raise api_error("NOT_FOUND", f"Dataset {dataset_id} not found", 404)
    return ok(_dataset_out(ds))
