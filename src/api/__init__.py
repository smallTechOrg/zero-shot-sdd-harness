import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def _lifespan(app: FastAPI):
    import structlog
    from config.settings import get_settings
    from db.session import init_db

    settings = get_settings()

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            __import__("logging").getLevelName(settings.log_level)
        ),
    )

    os.makedirs("data", exist_ok=True)
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Data Analyst Agent", version="0.1.0", lifespan=_lifespan)

    from api.health import router as health_router
    from api.datasets import router as datasets_router
    from api.query import router as query_router
    from api.audit import router as audit_router

    app.include_router(health_router)
    app.include_router(datasets_router)
    app.include_router(query_router)
    app.include_router(audit_router)

    # Serve frontend static export at /app if it exists
    frontend_out = (
        Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
    )
    if frontend_out.exists():
        app.mount(
            "/app",
            StaticFiles(directory=str(frontend_out), html=True),
            name="frontend",
        )

    return app


app = create_app()
