"""Serve the exported Next.js UI from FastAPI (single process, single port).

The frontend is built as a static export (`frontend/out`) and mounted at `/`. API routes are
registered first, so only non-API paths fall through to the static files. A catch-all returns
index.html for client-side routes (SPA fallback) and 404s for missing assets.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from datachat.observability.events import get_logger


def _ui_dir() -> Path:
    # Configurable; defaults to <repo root>/frontend/out (…/src/datachat/api/ui.py → up 4).
    env = os.environ.get("DATA_ANALYST_UI_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "frontend" / "out"


def mount_ui(app: FastAPI) -> None:
    """Mount the exported UI at / if it has been built; otherwise log and skip."""
    ui_dir = _ui_dir()
    index = ui_dir / "index.html"
    if not index.is_file():
        get_logger().info("ui.skip", reason="not built", ui_dir=str(ui_dir))

        @app.get("/")
        async def _ui_missing():
            return JSONResponse(
                {
                    "ok": True,
                    "data": {
                        "message": "DataChat API is running. The web UI is not built — run "
                        "`cd frontend && npm install && npm run build`, then restart.",
                        "docs": "/docs",
                    },
                }
            )

        return

    # Serve hashed assets and other files directly from the export.
    app.mount("/_next", StaticFiles(directory=ui_dir / "_next"), name="next-assets")

    @app.get("/")
    async def _ui_index():
        return FileResponse(index)

    # SPA / static fallback: any non-API, non-asset path → the matching file or index.html.
    @app.get("/{path:path}")
    async def _ui_catch_all(path: str):
        candidate = ui_dir / path
        if candidate.is_file():
            return FileResponse(candidate)
        html = ui_dir / f"{path}.html"
        if html.is_file():
            return FileResponse(html)
        return FileResponse(index)

    get_logger().info("ui.mounted", ui_dir=str(ui_dir))
