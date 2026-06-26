# Architecture

## System Overview

The data-analysis agent is a single-origin web application: a FastAPI backend serves both the REST API and the pre-built Next.js static export from `frontend/out/`. There is no separate frontend server in production. The user's browser communicates exclusively with the FastAPI process on port 8001. Data never leaves the user's machine — all CSV data is loaded into a local SQLite file at `data/agent.db`.

## Component Map

```
Browser
  │  GET /app/          → FastAPI serves frontend/out/ (Next.js static export)
  │  POST /upload       → FastAPI (CSV → SQLite dynamic table)
  │  POST /query        → FastAPI → LangGraph pipeline → Gemini → SQLite → response
  └─────────────────────────────────────────────────────────────────────────────────

FastAPI (src/)
  ├── api/upload.py      POST /upload
  ├── api/query.py       POST /query
  ├── api/health.py      GET /health
  │
  ├── graph/             LangGraph 5-node pipeline (see spec/agent.md)
  │   ├── state.py       AgentState TypedDict
  │   ├── nodes.py       schema_introspection, sql_generation, sql_execution,
  │   │                  chart_selection, insight_generation, handle_error, finalize
  │   ├── edges.py       conditional routing (error → handle_error, else → next node)
  │   ├── agent.py       graph assembly + compile()
  │   └── runner.py      run_analysis(session_id, question) → AnalysisResult
  │
  ├── db/
  │   ├── models.py      UploadSession, QueryRun (SQLAlchemy ORM)
  │   └── session.py     SQLite engine + session factory
  │
  ├── config/settings.py AGENT_* env vars + LANGCHAIN_* env vars
  ├── observability/     structlog configuration + get_logger()
  └── prompts/           SQL-generation system prompt (Markdown)

SQLite  data/agent.db
  ├── upload_sessions    (metadata, Alembic-managed)
  ├── query_runs         (query history, Alembic-managed)
  └── <dynamic tables>   one per upload: {slug}_{session_id[:8]}
                         e.g. sales_data_a3f7b2c1
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| API (`src/api/`) | Validate HTTP requests, invoke domain logic, serialize responses |
| Domain (`src/domain/`) | Pydantic request/response models; no business logic |
| Graph pipeline (`src/graph/`) | LangGraph 5-node sequential pipeline — schema, SQL gen, SQL exec, chart, insight |
| LLM client (`langchain-google-genai`) | Gemini calls with automatic LangSmith tracing |
| Data (`src/db/`) | SQLAlchemy ORM for metadata tables; raw DDL for dynamic CSV tables |
| Config (`src/config/`) | `pydantic-settings` Settings class; all env vars with AGENT_ prefix |
| Observability (`src/observability/`) | structlog JSON logs + LangSmith trace env vars |
| Frontend (`frontend/`) | Next.js static export; served by FastAPI at `/app` |

## Data Flow

1. **Upload:** User picks a CSV file in the browser → `POST /upload` (multipart) → backend parses the CSV, infers column types, creates `{slug}_{session_id[:8]}` table in SQLite, bulk-inserts rows, writes `UploadSession` row → returns `{session_id, table_name, schema}` to browser.

2. **Query:** User types a question → `POST /query {session_id, question}` → backend looks up `UploadSession.table_name` → calls `run_analysis(table_name, question)`.

3. **Pipeline:** LangGraph executes the five nodes in sequence:
   - `schema_introspection` reads column names and types from `PRAGMA table_info(table_name)`.
   - `sql_generation` calls Gemini with the schema + question → returns a SELECT query string.
   - `sql_execution` applies the SQL safety guard (block DDL/DML keywords), executes the SELECT, returns rows as a list of dicts.
   - `chart_selection` inspects row count and column types → chooses chart type (bar/line/pie/scatter) and builds a Recharts-compatible JSON spec.
   - `insight_generation` calls Gemini with the question + rows + chart type → returns a plain-English paragraph.

4. **Response:** Backend writes `QueryRun` record, returns `{query_run_id, sql, chart_spec, insight}`.

5. **Render:** Browser renders SQL in a code block, instantiates the Recharts component from `chart_spec`, and displays the insight paragraph.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini API (`gemini-2.5-flash`) | SQL generation + insight generation | Structured error returned; `QueryRun.status = "failed"` written; user sees error message |
| LangSmith | Distributed tracing of graph nodes and LLM calls | Tracing is fire-and-forget; agent continues if LangSmith is unreachable |
| SQLite (`data/agent.db`) | Metadata storage + dynamic data tables | Startup fails loudly if the `data/` directory is not writable |

## Stack

> This project's concrete technology choices. Generic rules live in `harness/patterns/tech-stack.md`; this section is only what this project picked.

- **Language:** Python 3.12+
- **Agent framework:** LangGraph `>=0.1` — five-node sequential pipeline with a conditional error branch; see `spec/agent.md`
- **LLM provider + model:** Google Gemini via `langchain-google-genai` (NOT raw `google-genai`). Default model: `gemini-2.5-flash`. Configurable via `AGENT_LLM_MODEL`.
- **Backend:** FastAPI `>=0.115` + Uvicorn `[standard]>=0.30`. Dev port: **8001**.
- **Database + ORM:** SQLite (`data/agent.db`) + SQLAlchemy `>=2.0` (sync). Driver: built-in `pysqlite` — no extra package. Alembic `>=1.13` for schema migrations.
- **Frontend:** Next.js 15.3.0 + React 19, TypeScript, Tailwind v4. Static export (`output: 'export'`, `basePath: '/app'`). Served by FastAPI at `/app`. `postcss.config.mjs` required for Tailwind v4. `NODE_OPTIONS=--no-experimental-webstorage` in build/dev scripts.
- **Charts:** `recharts ^2.x` (runtime dependency in `frontend/package.json`)
- **Dependency management:** `uv` (Python / `pyproject.toml`) · `pnpm` (frontend / `package.json`)

| Key library | Version | Purpose |
|-------------|---------|---------|
| `langchain-google-genai` | `>=2.0` | LangChain-wrapped Gemini; auto-traces to LangSmith |
| `python-multipart` | `>=0.0.9` | FastAPI file upload (multipart/form-data) |
| `langgraph` | `>=0.1` | Agent graph orchestration |
| `structlog` | `>=24.1` | Structured JSON logging |
| `pydantic-settings` | `>=2.3` | Settings from env / `.env` with `extra="ignore"` |
| `alembic` | `>=1.13` | SQLite schema migrations for metadata tables |
| `recharts` | `^2.x` | Frontend chart rendering from JSON spec |
| `httpx` | `>=0.27` | `TestClient` in tests |

**Avoid:**
- Raw `google-genai` SDK in the graph nodes (use `langchain-google-genai` so LangSmith traces automatically).
- Any DDL/DML SQL execution in the `sql_execution` node — blocked by the safety guard.
- PostgreSQL or any remote DB — the constraint is SQLite-only, local.
- `pnpm dev` (port 3000) as the test/demo run path — `basePath: '/app'` causes 404 at `localhost:3000/`; always use the single-origin path via FastAPI at port 8001.

## Deployment Model

Local development server only (no cloud deployment in scope). Single process: `uv run python -m src` starts FastAPI + Uvicorn on port 8001. The frontend must be pre-built (`cd frontend && pnpm build`) before starting the backend for the full UI to appear.

> **Assumed:** `langchain-google-genai` and `python-multipart` are not yet in `pyproject.toml`. The code-generator for slice-a adds them to `[project.dependencies]`.

> **Assumed:** The existing `google-genai` SDK in `pyproject.toml` remains (used by `llm/providers/gemini.py` for the existing skeleton's `LLMClient`), but the graph nodes bypass `LLMClient` and use `langchain-google-genai` directly so LangSmith tracing works.
