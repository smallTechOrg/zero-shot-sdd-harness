"""Dataset upload + profile endpoints.

``POST /datasets`` accepts a multipart CSV/Excel upload, stores the raw file in
the managed store (``AGENT_DATASET_STORE_DIR``), loads it into a server-side
DataFrame via the shared ``DatasetStore``, profiles it (schema/dtypes/ranges/
quality flags — NEVER raw rows), persists a ``DatasetRow``, and returns the
profile. The raw file lives only in the local store and the in-memory frame.

Phase-2 management routes (list / rename / delete) are present as clearly
labelled 501 stubs so the frontend can show "coming in Phase 2" rather than a
crash.
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from analysis import profiler
from analysis.dataset_store import get_dataset_store, read_file
from api._common import api_error, ok
from config.settings import get_settings
from db.models import DatasetRow
from db.session import get_session
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.datasets")

_ALLOWED_SUFFIXES = {".csv", ".txt", ".xlsx", ".xls"}
_MAX_BYTES = 100 * 1024 * 1024  # ~100MB


@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    session: Session = Depends(get_session),
) -> dict:
    started = time.perf_counter()
    filename = file.filename or "upload.csv"
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise api_error(
            "BAD_REQUEST",
            f"Unsupported file type {suffix!r}. Upload a .csv or .xlsx file.",
            400,
        )

    raw = await file.read()
    if not raw:
        raise api_error("BAD_REQUEST", "Uploaded file is empty.", 400)
    if len(raw) > _MAX_BYTES:
        raise api_error("BAD_REQUEST", "File exceeds the 100MB size limit.", 400)

    settings = get_settings()
    store = get_dataset_store()
    dataset_id = str(uuid.uuid4())

    store_dir = Path(settings.dataset_store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)
    stored_path = store_dir / f"{dataset_id}{suffix}"
    stored_path.write_bytes(raw)

    # Load into a DataFrame and profile it. A parse failure on a wrong-format
    # file is a client error (400); a genuine internal failure is a 500.
    try:
        df = read_file(stored_path)
    except ValueError as exc:
        stored_path.unlink(missing_ok=True)
        raise api_error("BAD_REQUEST", f"Could not read the file: {exc}", 400)
    except Exception as exc:  # malformed CSV/Excel body
        stored_path.unlink(missing_ok=True)
        raise api_error("BAD_REQUEST", f"Malformed file: {exc}", 400)

    try:
        prof = profiler.profile(df)
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        _log.error("profile_failed", dataset_id=dataset_id, error=str(exc))
        raise api_error("PROFILE_FAILED", f"Failed to profile the dataset: {exc}", 500)

    # Cache the frame so the agent's node_execute reads it without re-loading.
    store.put(dataset_id, df)

    display_name = (name or "").strip() or filename
    row = DatasetRow(
        id=dataset_id,
        name=display_name,
        file_path=str(stored_path),
        row_count=int(prof["row_count"]),
        col_count=int(prof["col_count"]),
        profile_json=json.dumps(prof),
        size_bytes=len(raw),
    )
    session.add(row)
    session.flush()

    _log.info(
        "dataset_uploaded",
        dataset_id=dataset_id,
        name=display_name,
        rows=row.row_count,
        cols=row.col_count,
        bytes=len(raw),
        latency_ms=int((time.perf_counter() - started) * 1000),
    )

    return ok(
        {
            "dataset_id": dataset_id,
            "name": display_name,
            "row_count": row.row_count,
            "col_count": row.col_count,
            "profile": prof,
        }
    )


# --- Phase-2 stubs (clearly labelled, not crashes) --------------------------


def _phase2_stub(feature: str) -> None:
    raise api_error(
        "NOT_IMPLEMENTED",
        f"{feature} is coming in Phase 2 (persistent dataset library).",
        501,
    )


@router.get("/datasets")
def list_datasets() -> dict:
    _phase2_stub("Listing the dataset library")


@router.patch("/datasets/{dataset_id}")
def rename_dataset(dataset_id: str) -> dict:
    _phase2_stub("Renaming a dataset")


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: str) -> dict:
    _phase2_stub("Deleting a dataset")
