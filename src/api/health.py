from fastapi import APIRouter, Response
from src.config import get_settings
import src.api.main as _main_module

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict:
    if not _main_module._ready:
        response.status_code = 503
        return {"status": "starting", "stub_mode": get_settings().is_stub}
    return {
        "status": "ok",
        "stub_mode": get_settings().is_stub,
        "llm_provider": get_settings().resolved_llm_provider,
    }
