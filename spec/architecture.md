# Architecture

## System Overview

The CSV Data Analysis Assistant is a single-server application. The Next.js frontend (static export served at /app) communicates with a FastAPI backend via REST API. The backend runs a LangGraph agent that profiles uploaded CSV files and answers natural-language questions by generating and executing pandas code locally. Gemini (gemini-2.0-flash) is the LLM. SQLite stores session-scoped metadata (sessions, uploaded file references, conversation messages). No data persists after session end.

## Component Map

```
Browser (Next.js SPA at /app)
    ↓ REST API calls
FastAPI (src/api/)
    ↓ invokes
LangGraph Agent (src/graph/)
    ↓ pandas + exec()
Uploaded CSV files (temp dir, per-session)
    ↓ session metadata
SQLite DB (data/agent.db)

LangGraph Agent → Gemini API (schema/stats only — NO raw row values)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| Presentation | Next.js SPA: file upload, profile cards, chat UI, Plotly chart rendering |
| API | FastAPI routers: sessions, files (upload+profile), messages (Q&A) |
| Agent | LangGraph graph: profile_data → plan_and_code → execute_code → format_response |
| Execution | Sandboxed exec() runner: runs generated pandas code against in-memory DataFrames |
| Storage | SQLite (session metadata, conversation history); temp files (CSV uploads, per-session) |

## Data Flow

1. User uploads CSV → POST /sessions/{id}/files → FastAPI saves to temp dir → profile_data node computes schema+stats (NO LLM call) → profile stored in uploaded_files table → profile JSON returned to frontend
2. User asks question → POST /sessions/{id}/messages → plan_and_code node calls Gemini with schema+stats+conversation history (raw rows NEVER included) → generates pandas code → execute_code runs it in sandboxed exec() → format_response calls Gemini to produce prose answer → message + optional Plotly JSON returned

## Privacy Constraint

**Raw data row values NEVER leave the server.** The LLM receives only:
- Column names and dtypes
- Numeric statistics: min, max, mean, std, 25th/50th/75th percentile, null count
- Categorical: top-5 value_counts, null count
- Row count

The exec() sandbox only receives the uploaded DataFrames as local variables and a restricted set of safe imports (pandas, numpy, plotly).

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (google-genai) | Code generation + response formatting | Return error message to user; no retry in Phase 1 |
| SQLite (local) | Session metadata + conversation history | Fatal at startup if file unwritable |

## Stack

- **Language:** Python 3.11+
- **Agent framework:** LangGraph >= 0.1
- **LLM provider + model:** Gemini / `gemini-3.1-pro` (via google-genai >= 2.9.0); env-configurable via `AGENT_LLM_MODEL`. Cost-optimised: profile_data node makes NO LLM call; only plan_and_code and format_response call the LLM.
- **Backend:** FastAPI >= 0.115 + uvicorn[standard] >= 0.30
- **Database + ORM:** SQLite + SQLAlchemy 2.0 (session-only data; no persistence across server restarts)
- **Frontend:** Next.js 15.3.0 + TypeScript + Tailwind v4 + react-plotly.js for interactive charts
- **Dependency management:** uv + pyproject.toml

| Key library | Version | Purpose |
|-------------|---------|---------|
| fastapi | >= 0.115 | REST API framework |
| uvicorn[standard] | >= 0.30 | ASGI server |
| pydantic-settings | >= 2.3 | Settings from .env |
| sqlalchemy | >= 2.0 | ORM + session management |
| alembic | >= 1.13 | DB migrations |
| google-genai | >= 2.9.0 | Gemini LLM calls |
| langgraph | >= 0.1 | Agent graph orchestration |
| structlog | >= 24.1 | Structured logging |
| pandas | latest | CSV profiling + code execution context |
| plotly | latest | Chart JSON generation in exec() sandbox |

Additional frontend deps: react-plotly.js, plotly.js-dist-min

**Avoid:** Sending raw DataFrame rows to the LLM (privacy constraint). Using asyncio in the exec() sandbox. External databases (no PostgreSQL — SQLite only, session-scoped). PNG chart images (use Plotly JSON only).

## Deployment Model

Local development server. Run from repo root: `uv run python -m src`. Serves API on port 8001. Frontend is built as Next.js static export (`cd frontend && pnpm build`), served at /app by FastAPI's StaticFiles.
