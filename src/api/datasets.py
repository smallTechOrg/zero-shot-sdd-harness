import json

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import Dataset, AuditLog
from analytics.ingest import ingest_csv, IngestError

router = APIRouter()


@router.post("/datasets")
async def create_dataset(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    name = file.filename or "dataset.csv"
    if not name.lower().endswith(".csv"):
        raise api_error("BAD_REQUEST", "Only CSV files are supported in this phase.", 400)

    content = await file.read()

    ds = Dataset(name=name, duckdb_table="", schema_json="[]", row_count=0)
    session.add(ds)
    session.flush()  # allocate id
    table = f"ds_{ds.id.replace('-', '')}"

    try:
        row_count, schema = ingest_csv(content=content, table=table)
    except IngestError as exc:
        session.add(
            AuditLog(
                dataset_id=ds.id, operation="ingest", status="error",
                error_message=str(exc),
            )
        )
        session.flush()
        raise api_error("BAD_REQUEST", str(exc), 400)

    ds.duckdb_table = table
    ds.schema_json = json.dumps(schema)
    ds.row_count = row_count
    session.add(
        AuditLog(
            dataset_id=ds.id, operation="ingest", status="success",
            row_count=row_count,
        )
    )
    session.flush()

    return ok({
        "id": ds.id,
        "name": ds.name,
        "row_count": ds.row_count,
        "schema": schema,
    })


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_session)) -> dict:
    rows = session.execute(
        select(Dataset).order_by(Dataset.created_at.desc())
    ).scalars().all()
    return ok({
        "datasets": [
            {
                "id": d.id,
                "name": d.name,
                "row_count": d.row_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in rows
        ]
    })
