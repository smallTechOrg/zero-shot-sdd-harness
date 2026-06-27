from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import DatasetRow, AnalysisRow
from domain.analysis import AnalysisRequest, AnalysisResponse
from graph.runner import run_analysis

router = APIRouter()


@router.post("/analyses")
def create_analysis(
    req: AnalysisRequest,
    session: Session = Depends(get_session),
) -> dict:
    if not req.question or not req.question.strip():
        raise api_error("EMPTY_QUESTION", "Question must not be empty", 400)

    dataset = session.get(DatasetRow, req.dataset_id)
    if dataset is None:
        raise api_error("DATASET_NOT_FOUND", f"Dataset {req.dataset_id} not found", 400)

    result = run_analysis(req.dataset_id, req.question, dataset.file_path)

    return ok(AnalysisResponse(**result).model_dump())


@router.get("/analyses/{analysis_id}")
def get_analysis(
    analysis_id: str,
    session: Session = Depends(get_session),
) -> dict:
    row = session.get(AnalysisRow, analysis_id)
    if row is None:
        raise api_error("ANALYSIS_NOT_FOUND", f"Analysis {analysis_id} not found", 404)

    return ok(
        AnalysisResponse(
            analysis_id=row.id,
            dataset_id=row.dataset_id,
            question=row.question,
            answer_text=row.answer_text,
            chart_json=row.chart_json,
            status=row.status,
            error=row.error_message,
        ).model_dump()
    )
