import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import UploadRow, AnalysisRow
from domain.analysis import AnalysisRequest, AnalysisResponse
from graph.runner import run_analysis

router = APIRouter()

_VALID_TYPES = {"summary_stats", "trend_over_time", "top_bottom_n", "correlation", "nl_query"}


@router.post("/analyses")
def create_analysis(req: AnalysisRequest, session: Session = Depends(get_session)) -> dict:
    if req.analysis_type not in _VALID_TYPES:
        raise api_error(
            "INVALID_ANALYSIS_TYPE",
            f"analysis_type must be one of: {', '.join(sorted(_VALID_TYPES))}",
            400,
        )

    upload = session.get(UploadRow, req.upload_id)
    if upload is None:
        raise api_error("NOT_FOUND", f"Upload '{req.upload_id}' not found.", 404)

    # Insert pending row
    analysis = AnalysisRow(
        upload_id=req.upload_id,
        analysis_type=req.analysis_type,
        params_json=json.dumps(req.params),
    )
    session.add(analysis)
    session.flush()
    analysis_id = analysis.id

    # Commit the pending row before running so finalize can see and update it
    session.commit()

    # Run synchronously — finalize node writes the result back to DB
    run_analysis(req.upload_id, req.analysis_type, req.params, analysis_id)

    # Open a fresh session to pick up the committed finalize result
    from db.session import create_db_session as _fresh_session
    with _fresh_session() as fresh:
        analysis = fresh.get(AnalysisRow, analysis_id)
        table = None
        if analysis.table_json:
            try:
                table = json.loads(analysis.table_json)
            except Exception:
                table = None
        result = AnalysisResponse(
            analysis_id=analysis.id,
            status=analysis.status,
            summary=analysis.summary,
            chart_json=analysis.chart_json,
            table=table,
            error=analysis.error_message,
        ).model_dump()

    return ok(result)


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, session: Session = Depends(get_session)) -> dict:
    analysis = session.get(AnalysisRow, analysis_id)
    if analysis is None:
        raise api_error("NOT_FOUND", f"Analysis '{analysis_id}' not found.", 404)

    table = None
    if analysis.table_json:
        try:
            table = json.loads(analysis.table_json)
        except Exception:
            table = None

    return ok(
        AnalysisResponse(
            analysis_id=analysis.id,
            status=analysis.status,
            summary=analysis.summary,
            chart_json=analysis.chart_json,
            table=table,
            error=analysis.error_message,
        ).model_dump()
    )
