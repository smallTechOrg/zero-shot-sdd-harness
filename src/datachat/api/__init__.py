from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import os


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from datachat.db.session import init_db
    from datachat.llm.client import get_llm_client
    init_db()
    get_llm_client()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="DataChat", version="0.1.0", lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    from datachat.api import health, sessions, chat
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(chat.router)

    # Serve minimal HTML UI if no frontend dist is present
    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if os.path.isdir(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    else:
        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def index():
            from datachat.config.settings import get_settings
            provider = get_settings().resolved_llm_provider
            banner = ""
            if provider == "stub":
                banner = '<div style="background:#fbbf24;padding:12px;text-align:center;font-weight:bold;">⚠ STUB MODE — Set DATACHAT_GEMINI_API_KEY for live responses</div>'
            return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>DataChat</title></head>
<body>
{banner}
<h1>DataChat</h1>
<p>API running. See <a href="/docs">/docs</a> for the OpenAPI spec.</p>
</body>
</html>"""

    return app


app = create_app()
