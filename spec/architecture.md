# Architecture

## System Overview

A single local FastAPI service that serves a Next.js static UI at `/app`, ingests an uploaded CSV into a local SQLite database as a real table, and answers natural-language questions via a LangGraph analyst flow backed by Gemini. The user, the data, and the database all live on one machine; the only outbound network call is to the Gemini API. Sessions, datasets, Q&A turns, and a full audit log are persisted in the same SQLite database.

## Component Map

```
Browser (Next.js static UI @ /app)
    │  HTTP (REST, JSON)
    ▼
FastAPI app (api:app)
    │
    ├── /datasets        → CSV ingestion → SQLite table (data/ingest.py)
    ├── /sessions/{id}/ask → analyst graph (graph/runner.py)
    └── /sessions/{id}    → session + Q&A history read
    │
    ▼
LangGraph analyst flow (generate_sql → validate_sql → execute_sql → format_answer)
    │                                     │              │
    │                                     │              ▼
    │                                     │       read-only executor (data/executor.py)
    │                                     ▼              │
    │                              sql_guard (data/sql_guard.py)   ←─ security boundary
    ▼                                                    ▼
Gemini API (llm/client.py)                       SQLite DB (SQLAlchemy)
                                                  ├── meta tables: datasets, sessions, qa_turns, audit_log, runs
                                                  └── data tables: one per uploaded CSV (ds_<id>)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI | Upload, ask, render answer + result table; labelled stubs for later phases |
| API (`src/api/`) | HTTP endpoints; request/response shaping; calls runner + data helpers |
| Agent (`src/graph/`) | LangGraph analyst flow: generate → validate → execute → format |
| Data (`src/data/`) | Ingestion, schema summary, SQL guard, read-only executor, audit log |
| Storage (`src/db/`) | SQLAlchemy models + session; SQLite via `AGENT_DATABASE_URL` |
| LLM (`src/llm/`) | Gemini client (already wired) |

## Data Flow

1. Trigger: user uploads a CSV via `POST /datasets` (multipart).
2. Ingestion reads the CSV, infers column types, creates a data table `ds_<dataset_id>` in SQLite, inserts rows, records a `datasets` row and creates (or reuses) a `sessions` row. Returns dataset id, session id, table name, row count, column list.
3. User asks via `POST /sessions/{id}/ask` with a question. The runner loads the dataset's compact schema summary + a 5-row sample + recent Q&A context.
4. The analyst graph: `generate_sql` (Gemini) → `validate_sql` (guard rejects any non-read query) → `execute_sql` (read-only connection) → `format_answer` (Gemini writes prose). Every executed/attempted SQL is audit-logged.
5. Output: a `qa_turns` row is persisted; response carries the prose answer, the SQL used, the result columns + rows.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (google-genai) | Generate SQL, format the answer | Node sets `state["error"]`; graph routes to handle_error; API returns the error; turn marked failed |
| SQLite (local file) | Meta tables + uploaded data tables | Startup/ingest fails loudly; no fallback |

## Stack

> Concrete choices for this project. Generic rules live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.12 (backend), TypeScript (frontend).
- **Agent framework:** LangGraph (multi-step conditional flow) — already wired in the skeleton.
- **LLM provider + model:** Gemini via the `google-genai` SDK; default model `gemini-2.5-flash`. Key `AGENT_GEMINI_API_KEY` (env prefix `AGENT_`). Do NOT use the deprecated `google-generativeai` SDK.
- **Backend:** FastAPI (`api:app`), served by uvicorn on port 8001.
- **Database + ORM:** SQLite + SQLAlchemy 2.0; production DB is the SQLite file at `AGENT_DATABASE_URL`. Uploaded CSVs become real tables in that same file. Migrations via Alembic.
- **Frontend:** Next.js 15 + React 19, static export → `frontend/out/`, served at `/app`.
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| pandas | latest | Read CSV/Excel, infer dtypes for ingestion |
| openpyxl | latest | Excel (`.xlsx`) reading via pandas |
| sqlalchemy | 2.0 | ORM + Core for ingestion and read-only execution |
| langgraph | (skeleton) | Analyst graph |
| google-genai | (skeleton) | Gemini calls |
| recharts | latest | Charts (Phase 2 — frontend) |

**Avoid:** the deprecated `google-generativeai` SDK; any ORM write path for uploaded data tables (uploaded tables are read-only after ingest); dumping full table contents into prompts; substituting Postgres/another DB — SQLite IS the production DB here.

## Deployment Model

A single long-running local process: `uv run python -m src` starts uvicorn on port 8001, serving both the JSON API and the static UI at `/app`. Build the UI first with `cd frontend && pnpm build`.

## Internal Interface Contract

The crisp helper signatures that `backend-agent-api` codes against (so it parallelizes with `backend-data`) are defined in [api.md](api.md#internal-interface-contract-phase-1).
