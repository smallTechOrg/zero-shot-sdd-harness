# Tech Stack

Approved at intake for FR-001 (Data Analyst Agent) on 2026-06-22.
All decisions below were confirmed by the user during the intake conversation.

---

## Language

**Python 3.12+** with `uv` as package manager.

## Agent Framework

**LangGraph** — analyst reasoning loop (clarify → generate SQL → execute → explain →
suggest follow-ups).

## LLM Provider

**Provider:** Google Gemini
**Model:** `gemini-2.5-flash`
**Env var:** `ANALYST_LLM_MODEL` (defaults to `gemini-2.5-flash`; never hardcoded)
**API key env var:** `GEMINI_API_KEY`
**SDK:** LangChain `init_chat_model` via `langchain-google-genai` (provider-agnostic; switching provider is a config change, not a code change)
**Recipe env prefix:** `APP_` in the scaffold; the executor renames this to `ANALYST_` when adapting the recipe (replaces all `APP_` / `app_` occurrences with `ANALYST_` / `analyst_`)

Safe defaults (2026):

| Provider | Default model |
|----------|--------------|
| Anthropic | `claude-3-5-haiku-latest` |
| OpenAI | `gpt-4o-mini` |
| Google Gemini | `gemini-2.5-flash` |

## Backend Framework

**FastAPI** — async, typed, fast. Port **8001**.

## Database

**DuckDB** (analytics / columnar) — in-process, file-backed. Handles CSV and JSON ingestion
natively. No server required. Primary store for uploaded datasets and SQL execution.

**SQLite** (spine) — lightweight relational store for session metadata, conversation history,
and the audit log. Runs alongside DuckDB.

Recipe: `python-fastapi-duckdb` (DuckDB primary + SQLite spine).

Both stores bootstrap schema via `create_tables()` at startup. No migrations shipped for
this milestone.

## Frontend

**Next.js 15** — required for Chart.js integration and dashboard rendering. Communicates
with the FastAPI backend over REST.

## Key Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| fastapi | latest | HTTP layer |
| uvicorn | latest | ASGI server |
| langgraph | latest | Analyst reasoning loop |
| duckdb | latest | Analytics database / CSV + JSON ingestion |
| langchain | latest | LLM abstraction layer |
| langchain-google-genai | latest | Gemini provider for LangChain |
| sqlalchemy[asyncio] | 2.x | SQLite async ORM (metadata spine) |
| aiosqlite | latest | async SQLite driver |
| pydantic-settings | latest | Config / env var management |
| pytest + pytest-asyncio | latest | Tests |
| httpx | latest | Async HTTP client for tests |

Frontend:

| Library | Version | Purpose |
|---------|---------|---------|
| next | 15 | Frontend framework |
| react | 18 | UI components |
| chart.js | latest | Chart rendering |
| react-chartjs-2 | latest | React bindings for Chart.js |

## What to Avoid

- Sending raw data rows to the LLM — schema-only prompts are a primary constraint.
- Hardcoded model names — always use `ANALYST_LLM_MODEL` env var.
- PostgreSQL or any server-side database — this is a local-first project; DuckDB + SQLite only.
- Alembic — not used; `create_tables()` at startup is sufficient for this milestone.
- Sending raw data rows to the LLM (already listed above — duplicated here for emphasis).
- Accessing DuckDB via SQLAlchemy — use the native `duckdb` Python driver directly for analytics queries.
- `git add -A` or committing `.env` files.

---

## Permanent Rules

### Port: 8001

`src/__main__.py` starts on **port 8001**. README and `.env.example` reference
`http://localhost:8001`.

### Schema-only LLM prompts

The system MUST send only the dataset schema (column names and inferred types) to the LLM
when generating SQL — never raw data rows. This is the primary token-economy constraint.

### Phase 2 must pass with no API key

`ANALYST_LLM_PROVIDER=stub` must be set by default in the test environment. Phase 2 gate
fails if it requires a real `GEMINI_API_KEY`. The stub returns canned SQL and chart configs
for the golden-path scenario.

### Session persistence

Session state (DuckDB file path, conversation history, audit log) is stored on disk keyed
by `session_id`. A server restart must not destroy active sessions.

### Audit log — one row per SQL execution

Every SQL execution writes one row: `timestamp`, `session_id`, `natural_language_query`,
`generated_sql`, `rows_returned`, `duration_ms`, `prompt_tokens`, `completion_tokens`.
