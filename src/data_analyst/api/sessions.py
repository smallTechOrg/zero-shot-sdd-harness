from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from data_analyst.api._common import api_error, ok
from data_analyst.db.models import SessionRow, DatasetRow
from data_analyst.db.session import get_session
from data_analyst.domain.session import SessionCreate, SessionListItem, SessionResponse
from data_analyst.domain.dataset import DatasetResponse
from data_analyst.duckdb_engine import engine as duckdb_engine

router = APIRouter()


@router.post("/sessions", status_code=201)
def create_session(
    body: SessionCreate | None = None,
    db: Session = Depends(get_session),
) -> dict:
    title = (body.title if body else None) or "New Session"
    row = SessionRow(title=title)
    db.add(row)
    db.flush()
    return ok(SessionResponse(
        session_id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    ).model_dump())


@router.get("/sessions")
def list_sessions(db: Session = Depends(get_session)) -> dict:
    rows = db.query(SessionRow).order_by(SessionRow.created_at.desc()).all()
    items = []
    for row in rows:
        items.append(SessionListItem(
            session_id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            message_count=len(row.messages),
            dataset_count=len(row.datasets),
        ).model_dump())
    return ok(items)


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: str,
    db: Session = Depends(get_session),
) -> dict:
    row = db.get(SessionRow, session_id)
    if row is None:
        raise api_error("session_not_found", f"Session {session_id} not found", 404)
    # Lazy re-register datasets in DuckDB
    if row.datasets:
        duckdb_engine.reregister_session_datasets(row.datasets)
    return ok(SessionResponse(
        session_id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    ).model_dump())


@router.get("/sessions/{session_id}/datasets")
def list_datasets(
    session_id: str,
    db: Session = Depends(get_session),
) -> dict:
    row = db.get(SessionRow, session_id)
    if row is None:
        raise api_error("session_not_found", f"Session {session_id} not found", 404)
    items = []
    for ds in row.datasets:
        items.append(DatasetResponse(
            dataset_id=ds.id,
            session_id=ds.session_id,
            original_filename=ds.original_filename,
            table_name=ds.table_name,
            file_format=ds.file_format,
            row_count=ds.row_count,
            registered_at=ds.registered_at,
        ).model_dump())
    return ok(items)
