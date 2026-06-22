import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings

# Readiness flag — set to True only after DB bootstrap completes (P1-AC7).
_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ready
    settings = get_settings()

    # Validate key if live provider requested [P1-AC6]
    if settings.resolved_llm_provider == "gemini" and not settings.gemini_api_key.get_secret_value():
        raise ValueError("DAA_GEMINI_API_KEY required when DAA_LLM_PROVIDER=gemini")

    # Ensure data dir exists [C-DB-DIRNAME]
    data_dir = os.path.dirname(settings.duckdb_path)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)

    # Bootstrap SQLite schema (imported here so tests can patch before import)
    from src.db.sqlite import create_tables_sqlite
    await create_tables_sqlite()

    _ready = True
    yield
    _ready = False


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Data Analyst Agent", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from src.api.health import router as health_router
    app.include_router(health_router)

    from src.api.sessions import router as sessions_router
    app.include_router(sessions_router)

    from src.api.datasets import router as datasets_router
    app.include_router(datasets_router)

    return app


app = create_app()
