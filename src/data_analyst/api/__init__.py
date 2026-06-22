from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from data_analyst.db.session import init_db
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Data Analyst Agent", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from data_analyst.api import sessions, upload, audit_api, query
    app.include_router(sessions.router)
    app.include_router(upload.router)
    app.include_router(audit_api.router)
    app.include_router(query.router)

    return app


app = create_app()
