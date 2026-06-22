from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from data_analyst.config.settings import get_settings
    from data_analyst.db.session import init_db
    from data_analyst.observability import configure_logging

    configure_logging(get_settings().log_level)
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Senior Data Analyst Agent", version="0.1.0", lifespan=_lifespan)

    from data_analyst.api import audit, datasets, health, sessions, web

    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(datasets.router)
    app.include_router(audit.router)
    app.include_router(web.router)
    return app


app = create_app()
