from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.api.datasets import router as datasets_router
from src.api.health import router as health_router
from src.api.query import router as query_router
from src.api.ui import router as ui_router
from src.db.connection import get_db, restore_views
from src.db.schema import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_db()
    create_tables(conn)
    restore_views(conn)
    conn.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Analyst",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(ui_router)
    app.include_router(datasets_router)
    app.include_router(query_router)
    return app


app = create_app()
