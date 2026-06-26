"""Sessions API.

POST /sessions                      — upload CSV, create in-memory session
POST /sessions/{session_id}/questions — ask a question, run analysis
GET  /sessions/{session_id}/runs/{run_id} — fetch a run
"""
import io
import json

import pandas as pd

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from api._common import ok, api_error
from db.session import create_db_session
from db.models import SessionRow, AnalysisRun
from sessions.store import put as put_session
from sessions.store import get as get_session
from graph.runner import run_analysis
from observability.events import get_logger

router = APIRouter()
_log = get_logger("api.sessions")

_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/sessions")
async def create_session(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "upload.csv"
    if not filename.lower().endswith(".csv"):
        raise api_error("INVALID_CSV", "Only .csv files are accepted.", 400)

    content = await file.read()
    if len(content) == 0:
        raise api_error("INVALID_CSV", "Uploaded file is empty.", 400)
    if len(content) > _MAX_BYTES:
        raise api_error("FILE_TOO_LARGE", "File exceeds the 50 MB limit.", 413)

    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise api_error("PARSE_ERROR", f"Failed to parse CSV: {exc}", 400)

    if df.empty or len(df.columns) == 0:
        raise api_error("INVALID_CSV", "CSV file has no data rows or columns.", 400)

    column_schema = [{"name": col, "dtype": str(df[col].dtype)} for col in df.columns]

    # Persist session metadata to DB
    with create_db_session() as db:
        row = SessionRow(
            original_filename=filename,
            row_count=len(df),
            column_schema=json.dumps(column_schema),
        )
        db.add(row)
        db.flush()
        session_id = row.id

    # Store DataFrame in-memory
    put_session(session_id, df)

    _log.info(
        "session.created",
        session_id=session_id,
        filename=filename,
        row_count=len(df),
        col_count=len(df.columns),
    )

    return ok({
        "session_id": session_id,
        "columns": column_schema,
        "row_count": len(df),
    })


class QuestionRequest(BaseModel):
    question: str


@router.post("/sessions/{session_id}/questions")
def ask_question(session_id: str, req: QuestionRequest) -> dict:
    if not req.question or not req.question.strip():
        raise api_error("EMPTY_QUESTION", "Question must not be empty.", 400)

    # Check session exists in memory
    if get_session(session_id) is None:
        raise api_error(
            "SESSION_NOT_FOUND",
            f"Session {session_id} not found. It may have expired (server restarted). "
            "Please re-upload your CSV.",
            404,
        )

    try:
        run_id = run_analysis(session_id, req.question.strip())
    except Exception as exc:
        _log.error("question.error", session_id=session_id, error=str(exc))
        raise api_error("INTERNAL_ERROR", f"Analysis failed: {exc}", 500)

    # Fetch the persisted run
    with create_db_session() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None:
            raise api_error("INTERNAL_ERROR", "Run not found after creation.", 500)

        if run.status == "failed":
            raise api_error("ANALYSIS_FAILED", run.error_message or "Analysis failed.", 502)

        chart_base64 = None
        chart_type = None
        if run.chart_data:
            cd = json.loads(run.chart_data)
            chart_base64 = cd.get("data")
            chart_type = cd.get("type")

        node_trace = json.loads(run.node_trace) if run.node_trace else []

        return ok({
            "run_id": run_id,
            "answer": run.answer,
            "chart_base64": chart_base64,
            "chart_type": chart_type,
            "executed_code": run.executed_code,
            "node_trace": node_trace,
            "tokens_in": run.tokens_in,
            "tokens_out": run.tokens_out,
            "cost_usd": run.cost_usd,
            "latency_ms": run.latency_ms,
        })


@router.get("/sessions/{session_id}/runs/{run_id}")
def get_run(session_id: str, run_id: str) -> dict:
    with create_db_session() as db:
        run = db.get(AnalysisRun, run_id)
        if run is None or run.session_id != session_id:
            raise api_error("RUN_NOT_FOUND", f"Run {run_id} not found.", 404)

        chart_base64 = None
        chart_type = None
        if run.chart_data:
            cd = json.loads(run.chart_data)
            chart_base64 = cd.get("data")
            chart_type = cd.get("type")

        node_trace = json.loads(run.node_trace) if run.node_trace else []

        return ok({
            "run_id": run.id,
            "session_id": run.session_id,
            "question": run.question,
            "answer": run.answer,
            "status": run.status,
            "chart_base64": chart_base64,
            "chart_type": chart_type,
            "executed_code": run.executed_code,
            "error_message": run.error_message,
            "node_trace": node_trace,
            "tokens_in": run.tokens_in,
            "tokens_out": run.tokens_out,
            "cost_usd": run.cost_usd,
            "latency_ms": run.latency_ms,
        })
