from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datachat.api.common import api_error, ok
from datachat.config.settings import get_settings
from datachat.db.models import QueryRow
from datachat.db.session import get_session
from datachat.pipeline.query_runner import run_query

router = APIRouter(prefix="/api/queries")


class QueryRequest(BaseModel):
    upload_id: str
    question: str


@router.post("")
def create_query(body: QueryRequest, session: Session = Depends(get_session)) -> dict:
    if not body.question.strip():
        raise api_error("empty_question", "Question must not be empty.")

    try:
        qrow = run_query(
            upload_id=body.upload_id,
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
        "upload_id": qrow.upload_id,
        "question": qrow.question,
        "answer": qrow.answer,
        "created_at": qrow.created_at.isoformat(),
    })


@router.get("/{query_id}")
def get_query(query_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.get(QueryRow, query_id)
    if row is None:
        raise api_error("not_found", "Query not found.", status_code=404)
    return ok({
        "id": row.id,
        "upload_id": row.upload_id,
        "question": row.question,
        "answer": row.answer,
        "created_at": row.created_at.isoformat(),
    })
