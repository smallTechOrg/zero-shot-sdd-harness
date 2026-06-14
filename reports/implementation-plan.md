# DataChat — v0.1 Implementation Plan

## Project
CSV Data Analysis Agent — upload a CSV, ask natural language questions, get text answers via Gemini.

## Stack
- Language: Python 3.11+ (uv)
- Framework: FastAPI + Uvicorn (port 8001)
- Database: SQLite via SQLAlchemy 2.x + Alembic
- LLM: Google Gemini (`google-generativeai`, model `gemini-2.5-flash`)
- Frontend: Jinja2 templates + vanilla JS
- Package: `src/datachat/`

---

## Phase 1 — Domain Models + DB Schema

**Goal:** All database models defined, migration applied, CRUD tests passing.

**Files to create:**
- `pyproject.toml`
- `alembic.ini`
- `alembic/script.py.mako`
- `alembic/env.py`
- `.env.example`
- `src/datachat/__init__.py`
- `src/datachat/config/settings.py`
- `src/datachat/db/models.py` — UploadRow + QueryRow
- `src/datachat/db/session.py`
- `src/datachat/domain/upload.py` — Upload Pydantic model
- `src/datachat/domain/query.py` — Query Pydantic model
- `tests/conftest.py`
- `tests/unit/test_smoke.py`
- `tests/unit/db/test_models.py`

**Alembic sequence:**
```
uv run alembic revision --autogenerate -m "initial"
uv run alembic upgrade head
uv run alembic current   # must show revision hash
```

**Gate:** `uv run pytest tests/unit/` — 100% pass against SQLite

**Commit:** `phase-1: domain models + schema — gate PASSED (N/N tests)`

---

## Phase 2 — Stubbed Agent Loop + Web UI

**Goal:** Full pipeline runs end-to-end (no real Gemini key required). Web UI served and functional in stub mode.

**Files to create:**
- `src/datachat/llm/providers/base.py` — abstract LLMProvider
- `src/datachat/llm/providers/stub.py` — deterministic stub, branches on `<node:query>` tag
- `src/datachat/llm/providers/gemini.py` — real Gemini provider
- `src/datachat/llm/providers/factory.py` — `create_llm_client()`, auto-selects real when `GEMINI_API_KEY` set
- `src/datachat/llm/client.py` — LLMClient wrapper
- `src/datachat/pipeline/csv_reader.py` — reads CSV, returns column names + sample rows
- `src/datachat/pipeline/query_runner.py` — builds prompt, calls LLM, saves to DB
- `src/datachat/api/__init__.py` — create_app() factory
- `src/datachat/api/_common.py` — ok(), api_error()
- `src/datachat/api/uploads.py` — POST /api/uploads, GET /api/uploads/{id}
- `src/datachat/api/queries.py` — POST /api/queries, GET /api/queries/{id}
- `src/datachat/api/pages.py` — GET / (serves index.html)
- `src/datachat/templates/index.html` — upload panel + query panel + stub banner
- `src/datachat/__main__.py` — `uvicorn.run()`
- `tests/integration/test_pipeline.py` — golden-path smoke test
- `README.md`

**Provider auto-selection rule:**
- `GEMINI_API_KEY` set → real Gemini provider
- `GEMINI_API_KEY` not set → stub provider + visible banner on every page

**Gate:**
```
uv run pytest                      # all tests pass, no GEMINI_API_KEY required
uv run python -m datachat          # server starts
curl http://localhost:8001/health   # 200
curl http://localhost:8001/         # 200, HTML rendered
```

**Commit:** `phase-2: stubbed agent loop + UI + README — gate PASSED (N/N tests)`

---

## Deferred to Future Phases
- Charts and visualizations (Phase 3)
- Auto-generated data insights (Phase 4)
- Multi-turn conversation history (Phase 5)
- Authentication
- Streaming responses
- Large file handling (>10k rows)
