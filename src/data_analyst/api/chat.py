import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from data_analyst.api._common import ok, api_error
from data_analyst.db.session import get_session
from data_analyst.domain.schemas import ChatRequest, ChatResponse
from data_analyst.duckdb_service import get_duckdb_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=dict, status_code=200)
async def chat(req: ChatRequest, db: Session = Depends(get_session)) -> dict:
    if not req.message or not req.message.strip():
        raise api_error("EMPTY_MESSAGE", "Message cannot be empty.", 422)

    from data_analyst.config.settings import get_settings
    settings = get_settings()

    if not settings.gemini_api_key:
        raise api_error(
            "NO_API_KEY",
            "GEMINI_API_KEY is not configured. Set DA_GEMINI_API_KEY or GEMINI_API_KEY in .env.",
            503,
        )

    duckdb_svc = get_duckdb_service()

    from data_analyst.agent.runner import run_turn
    try:
        result = run_turn(
            session_id=req.session_id,
            message=req.message,
            db=db,
            duckdb_svc=duckdb_svc,
            settings=settings,
        )
    except Exception as e:
        logger.exception("Agent run_turn failed: %s", e)
        raise api_error("AGENT_ERROR", f"Agent failed: {str(e)}", 502)

    return ok(
        ChatResponse(
            session_id=result.session_id,
            response_markdown=result.response_markdown,
            generated_sql=result.generated_sql,
            datasets_touched=result.datasets_touched,
            row_count_returned=result.row_count_returned,
            latency_ms=result.latency_ms,
        ).model_dump()
    )
