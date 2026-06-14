from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from datachat.db.session import init_db
    from datachat.config.settings import get_settings
    init_db()
    Path(get_settings().upload_dir).mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="DataChat", version="0.1.0", lifespan=_lifespan)

    from datachat.api.health import router as health_router
    from datachat.api.uploads import router as uploads_router
    from datachat.api.queries import router as queries_router
    from datachat.api.pages import router as pages_router

    app.include_router(health_router)
    app.include_router(uploads_router)
    app.include_router(queries_router)
    app.include_router(pages_router)

    return app


app = create_app()
