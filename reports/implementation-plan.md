# Implementation Plan — Senior Data Analyst Agent (v0.1)

**Slug:** `data-analyst`  ·  **Package:** `data_analyst`  ·  **Date:** 2026-06-22

## Scope (v0.1 — narrow core loop)

1. **Dataset management** — upload CSV/Parquet, register as tables in DuckDB + record in metadata, list/organise per session.
2. **NL cross-dataset query** — natural-language question → Gemini generates SQL → executed in DuckDB across one-or-more datasets → returned as formatted text + table.
3. **Audit logging** — every SQL/data operation persisted (timestamp, session, NL prompt, generated SQL, row count, duration) and viewable.

**Deferred to Future Phases:** charts, dashboards, deeper senior-analyst workflow simulation, ML, data-cleaning wizards.

## Stack

- Python 3.12, `uv` + `pyproject.toml`
- FastAPI + Jinja2 (server-rendered), Uvicorn, **port 8001**
- LangGraph agent: `plan → generate_sql → execute_sql → summarize → finalize` (+ `handle_error`)
- **Dual store:** DuckDB (`data/datasets.duckdb`) = analytical engine for user datasets; SQLite (`data/metadata.db`) via SQLAlchemy 2.0 + Alembic = agent metadata (sessions, datasets, messages, audit log)
- LLM: Google Gemini (`google-genai` SDK), default `gemini-2.5-flash`, escalate `gemini-2.5-pro`, `provider=auto` → offline stub when `DATA_ANALYST_GEMINI_API_KEY` unset
- Token economy: only schema + N sample rows to the LLM; never raw data; aggregates computed in DuckDB

## Build phases

### Phase 1 — Domain models + metadata schema
- `config/settings.py`, `domain/*.py` (Pydantic: Session, Dataset, Message, AuditLogEntry), `db/models.py` (SQLAlchemy), `db/session.py`
- Alembic: `script.py.mako`, `env.py`, `alembic.ini` → `revision --autogenerate -m "initial"` → `upgrade head` → verify `alembic current`
- Unit tests for CRUD on metadata store (SQLite, same driver as prod)
- **Gate:** `uv run alembic upgrade head` succeeds + `uv run pytest tests/unit` passes 100%

### Phase 2 — Stubbed agent loop end-to-end + web UI
- DuckDB tool layer (`tools/` or `duck/`), LangGraph nodes (stubbed Gemini via auto-stub), `graph/runner.py`
- LLM provider layer: `provider=auto`, offline stub (stub branches on explicit node tags), stub-mode banner on every page
- FastAPI app: health, create/list session, upload dataset, ask question, view audit log; Jinja2 pages
- `README.md` (commands from repo root, `uv run` prefixed, includes `alembic upgrade head` + `alembic current`)
- Golden-path UI smoke test (TestClient, asserts content) + live-server `/health` + one page curl
- **Gate:** `uv run pytest` passes with NO Gemini key set (DB URL set); smoke + live-server green; audit log written for the stubbed query
