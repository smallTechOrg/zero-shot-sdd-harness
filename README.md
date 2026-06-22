# Data Analyst Agent

A local-first NL-to-SQL agent. Upload a CSV, JSON, or Parquet file, then ask plain-English questions. The backend translates your question to SQL via Google Gemini, runs it against DuckDB, and returns both the raw results and a prose answer.

> **All commands run from the repo root.**

## Quick Start

### 1. Install all dependencies

```bash
make install
# or manually:
uv sync && cd frontend && npm install
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set ANALYST_GEMINI_API_KEY=your-key-here
# Without a key the backend runs in stub mode (fixed SQL + answer, no API calls)
```

### 3. Apply database migrations

```bash
uv run alembic upgrade head
uv run alembic current    # must show a revision hash — blank = migration not applied
```

### 4. Run the development server

```bash
make dev
# Starts backend on http://localhost:8001 and frontend on http://localhost:3000
```

Or run each separately:

```bash
# Backend only (port 8001):
make backend
# uv run uvicorn src.data_analyst.api:app --host 0.0.0.0 --port 8001 --reload

# Frontend only (port 3000):
make frontend
# cd frontend && npm run dev
```

---

## Running Tests

```bash
make test
# or individually:
uv run pytest tests/ -v            # backend — no GEMINI_API_KEY needed
cd frontend && npm test -- --run   # frontend
```

---

## Environment Variables

All variables use the `ANALYST_` prefix. Copy `.env.example` to `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANALYST_GEMINI_API_KEY` | `` | Google Gemini API key (empty = stub mode) |
| `ANALYST_DATABASE_URL` | `sqlite:///./data/session.db` | SQLite URL for sessions/messages/datasets |
| `ANALYST_DATA_DIR` | `./data` | Directory for uploaded files and audit log |
| `ANALYST_GEMINI_LLM_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `ANALYST_TOKEN_BUDGET_HARD_CAP` | `32000` | Hard cap on estimated prompt tokens |
| `ANALYST_BACKEND_PORT` | `8001` | Backend HTTP port |
| `ANALYST_FRONTEND_PORT` | `3000` | Frontend dev server port |

**Stub mode:** When `ANALYST_GEMINI_API_KEY` is not set, the backend stubs all LLM calls. The stub returns `SELECT COUNT(*) AS row_count FROM data` as SQL and a fixed prose answer. This lets the entire test suite pass without any API key.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sessions` | Create a new session |
| `GET` | `/sessions` | List all sessions |
| `GET` | `/sessions/{id}` | Get session detail |
| `GET` | `/sessions/{id}/datasets` | List datasets in session |
| `POST` | `/sessions/{id}/upload` | Upload CSV/JSON/Parquet file |
| `POST` | `/sessions/{id}/query` | Ask a natural-language question |
| `GET` | `/audit` | Read audit log (filterable by session_id) |

### Example: upload a file

```bash
curl -X POST http://localhost:8001/sessions/SESSION_ID/upload \
  -F "file=@data.csv"
```

### Example: ask a question

```bash
curl -X POST http://localhost:8001/sessions/SESSION_ID/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total value?"}'
```

---

## Project Layout

```
src/data_analyst/
  api/              FastAPI routers (sessions, upload, query, audit)
  audit/            JSONL audit logger
  config/           Pydantic BaseSettings (ANALYST_ prefix)
  db/               SQLAlchemy models + session factory (SQLite)
  domain/           Pydantic request/response schemas
  duckdb_engine/    DuckDB in-process engine for analytical queries
  llm/              Gemini client, SQL extractor, token budget helpers
frontend/           React 18 + Vite 5 + Tailwind (port 3000)
tests/
  unit/             Unit tests (no DB, no LLM)
  integration/      Integration tests via FastAPI TestClient
alembic/            SQLite schema migrations
```

---

## Architecture Notes

- **SQLite** (via SQLAlchemy 2.x + Alembic): stores sessions, messages, dataset metadata
- **DuckDB** (in-process): runs analytical SQL against uploaded files
- **Gemini API** (google-generativeai SDK): generates SQL and prose answers; stubbed offline
- **No LangGraph, no pandas, no ReAct loop** — direct pipeline: question → SQL → results → answer
