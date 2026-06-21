from fastapi import APIRouter
from src.config import get_settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.env,
        "llm_provider": settings.resolved_llm_provider,
        "stub_mode": settings.is_stub,
    }
