# Data Analyst Agent

> All commands run from the repo root.

A fully-local, multi-user data analyst powered by Gemini. Upload CSV/Excel files, ask natural-language questions, get SQL-backed answers with an audit trail.

## What It Does

- Upload CSV or Excel (.xlsx/.xls) datasets per session
- Ask natural-language questions — Gemini 2.5 Flash translates them to SQLite SQL via structured tool-use
- Get formatted markdown answers with data tables
- Sessions are namespaced — each session's data is isolated
- Every SQL query logged with timestamp, SQL text, row count, and latency
- Schema-only context injection — raw data rows never sent to the LLM

## Quick Start

### 1. Prerequisites

- Python 3.12+ and `uv` (`pip install uv`)
- Node.js 18+ and `pnpm` (`npm i -g pnpm`)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env: set AGENT_GEMINI_API_KEY=your_key_here
```

### 3. Install Python dependencies

```bash
uv sync
```

### 4. Run database migrations

```bash
uv run alembic upgrade head
uv run alembic current
```

`alembic current` must show `001 (head)`.

### 5. Build the frontend

```bash
cd frontend && pnpm install && pnpm build && cd ..
```

### 6. Start the server

```bash
uv run python -m src
```

The server starts on `http://localhost:8001`.

### 7. Open the UI

Open `http://localhost:8001/app/` in your browser.

## Run Tests

```bash
# Unit tests only (no LLM key required)
uv run pytest tests/unit/ tests/phase1/ -q

# All tests including integration (requires AGENT_GEMINI_API_KEY)
uv run pytest tests/ -x -q
```

## API Endpoints

All endpoints that operate on session data require the `X-Session-ID` header.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| POST | `/datasets/upload` | Upload a CSV or Excel file (multipart) |
| GET | `/datasets` | List datasets for a session |
| POST | `/query` | Run a natural-language question against a dataset |
| GET | `/audit` | Query audit log for a session |
| GET | `/app/` | Web UI (static Next.js export) |

### POST /datasets/upload

Headers: `X-Session-ID: <session-id>`
Body: multipart/form-data with `file` field

Response:
```json
{
  "data": {
    "dataset_id": "...",
    "session_id": "...",
    "table_name": "...",
    "original_filename": "sales.csv",
    "row_count": 100,
    "column_names": ["product", "sales", "region"],
    "created_at": "2026-06-23T09:00:00+00:00"
  },
  "error": null
}
```

### POST /query

Headers: `X-Session-ID: <session-id>`
Body:
```json
{
  "question": "What is the total sales by region?",
  "dataset_table": "<table_name from upload>"
}
```

Response:
```json
{
  "data": {
    "answer": "...",
    "table": [...],
    "sql": "SELECT region, SUM(sales) ...",
    "audit_id": "..."
  },
  "error": null
}
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENT_GEMINI_API_KEY` | Yes | — | Gemini API key |
| `AGENT_DATABASE_URL` | No | `sqlite:///./data/agent.db` | SQLite database path |
| `AGENT_LLM_MODEL` | No | `gemini-2.5-flash` | Gemini model name |
| `AGENT_LOG_LEVEL` | No | `INFO` | Log level |
| `PORT` | No | `8001` | Server port |

## Project Structure

```
src/                  Python package (FastAPI + LangGraph backend)
  api/                FastAPI routers (health, datasets, query, audit)
  config/             Settings (AGENT_ prefix)
  db/                 SQLAlchemy models + session
  graph/              LangGraph analyst pipeline (nodes, state, edges, agent)
  ingest/             CSV/Excel parser + SQLite loader
  llm/                Gemini provider wrapper
  prompts/            LLM prompt templates
frontend/             Next.js 15 static export
  src/app/            App routes and layout
  src/components/     UI components
alembic/              Database migrations
tests/                pytest tests (unit + integration)
  unit/               No LLM key required
  phase1/             Phase 1 gate tests
  integration/        Real LLM + DB (requires AGENT_GEMINI_API_KEY)
  e2e/                End-to-end tests (Phase 2 — coming soon)
spec/                 Agent spec files
data/                 SQLite database (gitignored)
```

## Stack

- **Backend:** Python 3.12 + FastAPI + LangGraph + google-genai (Gemini 2.5 Flash) + SQLite/SQLAlchemy + Alembic + pandas
- **Frontend:** Next.js 15 + React 19 + Tailwind CSS v4
- **Managed by:** `uv` (Python) + `pnpm` (frontend)

## Phase Status

- **Phase 1** (current) — CSV/Excel upload, NL querying via Gemini, SQLite execution, audit log, session isolation
- **Phase 2** — Chart visualisations, audit log UI viewer, session management UI
