from fastapi import APIRouter
from datachat.api._common import ok

router = APIRouter()


@router.get("/health")
def health():
    from datachat.config.settings import get_settings
    return ok({"status": "ok", "llm_provider": get_settings().resolved_llm_provider})
