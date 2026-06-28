from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from analysis.loader import LoaderError, load_dataset_metadata
from api._common import ok, api_error
from config.settings import get_settings
from db.models import Dataset
from db.session import get_session
from domain.dataset import DatasetResponse
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.datasets")

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def _upload_dir() -> Path:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return _UPLOAD_DIR


@router.post("/datasets")
async def create_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    settings = get_settings()
    filename = file.filename or "upload.csv"

    if not filename.lower().endswith(".csv"):
        raise api_error(
            "UNSUPPORTED_FORMAT",
            "Only CSV files are supported in this phase (.xlsx coming later).",
            415,
        )

    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise api_error(
            "FILE_TOO_LARGE",
            f"File exceeds the {settings.max_upload_mb}MB limit.",
            413,
        )

    # Create the row first to mint the id, then write <id>.csv.
    dataset = Dataset(filename=filename, path="", format="csv")
    session.add(dataset)
    session.flush()
    dataset_id = dataset.id

    dest = _upload_dir() / f"{dataset_id}.csv"
    dest.write_bytes(contents)

    try:
        profile = load_dataset_metadata(str(dest), sample_rows=settings.sample_rows)
    except LoaderError as exc:
        # Clean up the unusable file and the half-made row.
        dest.unlink(missing_ok=True)
        session.delete(dataset)
        raise api_error("PARSE_ERROR", f"Could not parse the CSV: {exc}", 422)

    dataset.path = str(dest)
    dataset.row_count = profile.row_count
    dataset.column_count = profile.column_count
    dataset.schema_json = profile.schema
    dataset.sample_rows_json = profile.sample_rows

    _log.info(
        "dataset_uploaded",
        dataset_id=dataset_id,
        filename=filename,
        rows=profile.row_count,
        columns=profile.column_count,
    )

    resp = DatasetResponse(
        id=dataset_id,
        filename=filename,
        row_count=profile.row_count,
        column_count=profile.column_count,
        schema_=profile.schema,
        sample_rows=profile.sample_rows,
    )
    return ok(resp.model_dump_api())
