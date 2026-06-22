from fastapi import APIRouter

from data_analyst.api._common import llm_provider_label

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_provider": llm_provider_label()}
