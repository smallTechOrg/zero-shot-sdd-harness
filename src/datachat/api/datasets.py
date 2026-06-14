import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datachat.api.common import api_error, ok
from datachat.config.settings import get_settings
from datachat.db.models import DashboardRow, DatasetQueryRow, DatasetRow, DatasetUploadRow, UploadRow
from datachat.db.session import get_session
from datachat.pipeline.csv_reader import read_csv_metadata
from datachat.pipeline.dashboard_generator import generate_dashboard
from datachat.pipeline.dataset_query_runner import run_dataset_query

router = APIRouter(prefix="/api/datasets")


class DatasetCreateRequest(BaseModel):
    name: str


class DatasetQueryRequest(BaseModel):
    question: str


def _dataset_out(ds: DatasetRow, uploads: list[UploadRow]) -> dict:
    return {
        "id": ds.id,
        "name": ds.name,
        "created_at": ds.created_at.isoformat(),
        "uploads": [
            {
                "id": u.id,
                "original_filename": u.original_filename,
                "row_count": u.row_count,
                "columns": u.columns,
            }
            for u in uploads
        ],
    }


def _get_dataset_uploads(dataset_id: str, session: Session) -> list[UploadRow]:
    join_rows = (
        session.query(DatasetUploadRow)
        .filter(DatasetUploadRow.dataset_id == dataset_id)
        .all()
    )
    uploads = [session.get(UploadRow, jr.upload_id) for jr in join_rows]
    return [u for u in uploads if u is not None]


# --- Dataset CRUD ---

@router.post("")
def create_dataset(body: DatasetCreateRequest, session: Session = Depends(get_session)) -> dict:
    if not body.name.strip():
        raise api_error("empty_name", "Dataset name must not be empty.")
    ds = DatasetRow(name=body.name.strip())
    session.add(ds)
    session.flush()
    return ok(_dataset_out(ds, []))


@router.get("")
def list_datasets(session: Session = Depends(get_session)) -> dict:
    datasets = session.query(DatasetRow).order_by(DatasetRow.created_at.desc()).all()
    result = []
    for ds in datasets:
        uploads = _get_dataset_uploads(ds.id, session)
        result.append(_dataset_out(ds, uploads))
    return ok(result)


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str, session: Session = Depends(get_session)) -> dict:
    ds = session.get(DatasetRow, dataset_id)
    if ds is None:
        raise api_error("not_found", "Dataset not found.", status_code=404)
    uploads = _get_dataset_uploads(dataset_id, session)
    return ok(_dataset_out(ds, uploads))


# --- Add a CSV to a dataset ---

@router.post("/{dataset_id}/uploads")
def add_upload_to_dataset(
    dataset_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    ds = session.get(DatasetRow, dataset_id)
    if ds is None:
        raise api_error("not_found", "Dataset not found.", status_code=404)

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

    upload = UploadRow(
        filename=safe_name,
        original_filename=file.filename,
        row_count=row_count,
        columns_json=json.dumps(columns),
    )
    session.add(upload)
    session.flush()

    join = DatasetUploadRow(dataset_id=dataset_id, upload_id=upload.id)
    session.add(join)
    session.flush()

    return ok({
        "dataset_id": dataset_id,
        "upload": {
            "id": upload.id,
            "original_filename": upload.original_filename,
            "row_count": upload.row_count,
            "columns": columns,
        },
    })


# --- Query a dataset across all its files ---

@router.post("/{dataset_id}/queries")
def query_dataset(
    dataset_id: str,
    body: DatasetQueryRequest,
    session: Session = Depends(get_session),
) -> dict:
    if not body.question.strip():
        raise api_error("empty_question", "Question must not be empty.")

    try:
        qrow = run_dataset_query(
            dataset_id=dataset_id,
            question=body.question,
            session=session,
            upload_dir=get_settings().upload_dir,
        )
    except ValueError as exc:
        raise api_error("not_found", str(exc), status_code=404)
    except Exception as exc:
        raise api_error("llm_error", f"Failed to generate answer: {exc}", status_code=500)

    return ok({
        "id": qrow.id,
        "dataset_id": qrow.dataset_id,
        "question": qrow.question,
        "answer": qrow.answer,
        "tokens": {
            "input": qrow.input_tokens,
            "output": qrow.output_tokens,
            "total": qrow.input_tokens + qrow.output_tokens,
        },
        "cost_usd": qrow.cost_usd,
        "created_at": qrow.created_at.isoformat(),
    })


@router.get("/{dataset_id}/queries")
def list_dataset_queries(dataset_id: str, session: Session = Depends(get_session)) -> dict:
    rows = (
        session.query(DatasetQueryRow)
        .filter(DatasetQueryRow.dataset_id == dataset_id)
        .order_by(DatasetQueryRow.created_at.desc())
        .all()
    )
    return ok([
        {
            "id": r.id,
            "question": r.question,
            "answer": r.answer,
            "tokens": {
                "input": r.input_tokens,
                "output": r.output_tokens,
                "total": r.input_tokens + r.output_tokens,
            },
            "cost_usd": r.cost_usd,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ])


# --- Dashboard ---

def _dashboard_out(row: DashboardRow) -> dict:
    return {
        "dataset_id": row.dataset_id,
        "insights": row.insights,
        "charts": row.charts,
        "tokens": {
            "input": row.input_tokens,
            "output": row.output_tokens,
            "total": row.input_tokens + row.output_tokens,
        },
        "cost_usd": row.cost_usd,
        "generated_at": row.generated_at.isoformat(),
    }


@router.post("/{dataset_id}/dashboard")
def generate_dataset_dashboard(
    dataset_id: str,
    session: Session = Depends(get_session),
) -> dict:
    """Generate (or regenerate) the dashboard for a dataset."""
    ds = session.get(DatasetRow, dataset_id)
    if ds is None:
        raise api_error("not_found", "Dataset not found.", status_code=404)

    try:
        row = generate_dashboard(
            dataset_id=dataset_id,
            session=session,
            upload_dir=get_settings().upload_dir,
        )
    except ValueError as exc:
        raise api_error("no_files", str(exc), status_code=400)
    except Exception as exc:
        raise api_error("generation_error", f"Failed to generate dashboard: {exc}", status_code=500)

    return ok(_dashboard_out(row))


@router.get("/{dataset_id}/dashboard")
def get_dataset_dashboard(
    dataset_id: str,
    session: Session = Depends(get_session),
) -> dict:
    """Return the cached dashboard, or 404 if not yet generated."""
    ds = session.get(DatasetRow, dataset_id)
    if ds is None:
        raise api_error("not_found", "Dataset not found.", status_code=404)

    row = session.get(DashboardRow, dataset_id)
    if row is None:
        raise api_error("not_generated", "Dashboard not yet generated.", status_code=404)

    return ok(_dashboard_out(row))
