from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from analyst.config.settings import get_settings
from analyst.db.session import init_db
from analyst.llm.gemini_client import GeminiClient
from analyst.llm.stub_client import StubGeminiClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()

    # Ensure data/datasets directory exists
    datasets_dir = Path(settings.data_dir) / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    if settings.resolved_llm_provider == "stub":
        app.state.stub_mode = True
        app.state.llm_provider = StubGeminiClient()
    else:
        app.state.stub_mode = False
        app.state.llm_provider = GeminiClient(
            settings.gemini_api_key, settings.llm_model
        )

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Data Analyst Agent", lifespan=lifespan)
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    from analyst.api import audit, datasets, health, query, sessions

    app.include_router(health.router)
    app.include_router(sessions.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")

    return app


app = create_app()
