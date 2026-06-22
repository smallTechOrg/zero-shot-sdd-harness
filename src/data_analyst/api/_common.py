from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates

from data_analyst.llm import get_llm_client

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


def ok(data: Any) -> dict:
    return {"data": data, "error": None}


def api_error(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def llm_provider_label() -> str:
    """'real' when Gemini is resolved, else 'stub' — matches the spec /health contract."""
    return "real" if get_llm_client().provider_name == "gemini" else "stub"


def render(request: Request, name: str, **ctx):
    """Starlette >= 1.0 TemplateResponse signature. Always inject llm_provider."""
    ctx.setdefault("llm_provider", llm_provider_label())
    return templates.TemplateResponse(request, name, ctx)
