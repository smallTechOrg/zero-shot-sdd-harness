"""FastAPI app factory + lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from datachat.api import conversations, datasets
from datachat.config.settings import get_settings
from datachat.db.session import init_db
from datachat.observability.events import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    settings.require_api_key()  # fail loud at startup — real-first, no stub
    settings.configure_provider_env()
    await init_db()
    get_logger().info("app.start", model=settings.llm_model, provider=settings.llm_provider)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="DataChat", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def _envelope_http_exc(_request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            return JSONResponse(detail, status_code=exc.status_code)
        return JSONResponse(
            {"ok": False, "error": {"code": "HTTP_ERROR", "message": str(detail)}},
            status_code=exc.status_code,
        )

    @app.get("/health")
    async def health():
        return {"ok": True, "data": {"status": "healthy"}}

    app.include_router(datasets.router)
    app.include_router(conversations.router)
    return app


app = create_app()
