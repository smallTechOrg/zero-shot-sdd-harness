from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

_templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    from datachat.llm.client import get_llm_client
    _, is_stub = get_llm_client()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"is_stub": is_stub},
    )
