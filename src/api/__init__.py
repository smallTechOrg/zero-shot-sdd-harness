from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from db.session import init_db
    init_db()
    yield


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Wrap HTTPException into our standard envelope: {data: null, error: {code, message}}."""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        error_body = {"code": detail["code"], "message": detail.get("message", str(exc))}
    else:
        error_body = {"code": "ERROR", "message": str(detail)}
    return JSONResponse(
        status_code=exc.status_code,
        content={"data": None, "error": error_body},
    )


def create_app() -> FastAPI:
    app = FastAPI(title="CSV Analysis Agent", version="0.1.0", lifespan=_lifespan)

    # Custom error handler — wraps HTTPException in our {data, error} envelope
    app.add_exception_handler(HTTPException, _http_exception_handler)

    from api import health, sessions, files, messages, export
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(files.router)
    app.include_router(messages.router)
    app.include_router(export.router)

    # CORS for frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8001"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve the built Next.js static export at /app
    # Run `cd frontend && pnpm build` to generate frontend/out/ before starting.
    # Server starts fine without it (API-only mode when out/ doesn't exist).
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
    if frontend_out.exists():
        app.mount("/app", StaticFiles(directory=str(frontend_out), html=True), name="frontend")

    # Root has no page of its own — send visitors to the UI when it's built, otherwise the API docs.
    root_redirect = "/app" if frontend_out.exists() else "/docs"

    @app.get("/", include_in_schema=False)
    async def _root() -> RedirectResponse:
        return RedirectResponse(url=root_redirect)

    return app


app = create_app()
