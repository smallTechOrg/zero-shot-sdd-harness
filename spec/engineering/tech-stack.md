# Tech Stack

> **Boilerplate status:** Filled in by the tech-designer sub-agent after the product spec is approved. The user may override specific choices before the tech-designer is invoked.

---

## Language

**Python 3.11+**

**Why:** Mature async support, first-class type hints, broad data-science library ecosystem (pandas, etc.), and strong FastAPI/SQLAlchemy integration. 3.11+ for improved performance and better error messages.

## Agent Framework

**None (custom pipeline)**

**Why:** DataChat v0.1 is a single-turn Q&A loop — the user uploads a CSV, asks a question, and gets a text answer. There is no multi-step planning, memory, or parallel tool use that would justify LangGraph or CrewAI. A lightweight custom pipeline keeps the dependency footprint small and the control flow obvious.

## LLM Provider

**Google Gemini** via the `google-generativeai` Python SDK.

**Model:** `gemini-2.5-flash` (configured via env var `DATACHAT_LLM_MODEL`; default to `gemini-2.5-flash` — see LLM Model Name Rule below).

**API key env var:** `GEMINI_API_KEY`

**Why:** User-specified. `gemini-2.5-flash` is the current safe default for Gemini (see Permanent Rules — LLM Model Name Rule). The model name must be overridable without a code change.

## Backend Framework (if applicable)

**FastAPI** with **Uvicorn** (`uvicorn[standard]`) as the ASGI server.

Serves both the JSON API endpoints and the Jinja2 HTML templates from a single process. Default dev port: **8001** (see Permanent Rules).

## Database (if applicable)

**SQLite** (file-based, local-only)

**ORM/ODM:** SQLAlchemy 2.x (sync ORM) + **Alembic** for migrations.

SQLite is appropriate because this project is local-only and has no concurrent-write requirements. The database file path is configurable via `DATACHAT_DATABASE_URL` (default: `sqlite:///./datachat.db`).

## Frontend (if applicable)

**Jinja2 templates** (served by FastAPI) + **vanilla JavaScript** (no build step, no npm).

Static assets (CSS, JS) live in `src/datachat/static/`. Templates live in `src/datachat/templates/`. No React, Vue, or bundler.

## Key Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `fastapi` | latest | Web framework — routes, dependency injection, request/response models |
| `uvicorn[standard]` | latest | ASGI server for FastAPI |
| `sqlalchemy` | 2.x | Sync ORM for SQLite; session management via `Depends()` |
| `alembic` | latest | Database migration management |
| `google-generativeai` | latest | Google Gemini LLM client |
| `python-multipart` | latest | Required by FastAPI for `UploadFile` (CSV uploads) |
| `jinja2` | latest | HTML template rendering |
| `pandas` | latest | CSV parsing and in-memory data manipulation |
| `pydantic-settings` | latest | Settings/config from env vars and `.env` file |
| `pytest` | latest | Test runner |
| `httpx` | latest | Async HTTP client used by FastAPI `TestClient` in tests |

## What to Avoid

- **No async SQLAlchemy** (`aiosqlite`, `asyncpg`, `AsyncSession`) in v0.1 — sync SQLAlchemy is simpler and SQLite has no concurrency benefit from async I/O.
- **No ORM for LLM prompts** — do not store raw prompt strings in the DB; only store structured metadata (session ID, question, answer text).
- **No React / Vue / Node.js build tooling** — the frontend must remain zero-build; plain `<script>` tags only.
- **No LangChain or agent frameworks** — keep the pipeline as a direct function call chain.
- **No bare `except`** — always catch specific exception types; log and re-raise or return a structured error.
- **No global mutable state** — all dependencies (DB session, LLM client, settings) are injected via FastAPI `Depends()`.
- **Do not hardcode the model name** — always read it from `settings.llm_model`; the default lives in `Settings`, not scattered across call sites.

## Dependency Management

**`uv`** with `pyproject.toml`.

All runtime commands are prefixed with `uv run` (e.g. `uv run uvicorn`, `uv run pytest`, `uv run alembic`). Install deps with `uv sync`. There is no `requirements.txt` — `pyproject.toml` is the single source of truth.

The SQLite driver (`sqlite3`) is part of the Python standard library; no extra driver package is needed. This satisfies the DB Driver Rule without a separate install step.

---

## Permanent Rules (apply to all projects, not filled in by tech-designer)

### Default Dev Port

All generated projects **must** use **port 8001** as the default development port (not 8000).

Reason: Port 8000 is commonly occupied by other local services (other FastAPI apps, Django, http.server, etc.). Using 8001 avoids startup failures with no code change needed.

- `__main__.py` must hard-code `port=8001` (not 8000) unless overridden by an env var
- README must reference `http://localhost:8001`
- `.env.example` should include `PORT=8001` if the port is configurable

### LLM Model Name Rule

**Always use a current, verified model name — never a deprecated or guessed one.**

- For Google Gemini: use **`gemini-2.0-flash`** as the default (not `gemini-1.5-flash` — deprecated and removed from the API).
- Model names change. Before hardcoding any model identifier, verify it exists by calling the provider's `ListModels` API or checking current documentation.
- The model name must be configurable via an env var (e.g. `APPNAME_LLM_MODEL`) so it can be changed without a code deployment.
- A 404 NOT_FOUND error from the LLM API almost always means the model name is wrong — check the name first before debugging anything else.

Current safe defaults (as of 2026):

| Provider | Default model | Notes |
|----------|---------------|-------|
| Google Gemini | `gemini-2.5-flash` | `gemini-2.0-flash` and `gemini-1.5-flash` unavailable for new users |
| OpenAI | `gpt-4o-mini` | |
| Anthropic | `claude-3-5-haiku-latest` | |

### DB Driver Rule

The database driver (e.g. `psycopg2-binary` for PostgreSQL, `asyncpg` for async PostgreSQL) **must be declared in the main `[project.dependencies]` block**, never in `[dependency-groups.dev]` or equivalent dev-only groups.

Reason: Alembic migrations run at deploy/setup time, not just in tests. If the driver is dev-only, `alembic upgrade head` fails in any environment that didn't install dev deps.

### Test Environment Rule

**Tests must use the same database driver as production.** If the production DB is PostgreSQL, tests run against PostgreSQL — not SQLite.

- Tests that pass on SQLite but were never run against PostgreSQL are **not a passing gate**.
- The test database must be set up automatically. Use `conftest.py` to create and tear down the test database. No manual steps.
- The test database URL is provided via environment variable (e.g. `TEST_DATABASE_URL` or reuse the app's `DATABASE_URL` pointing at a `_test` database). The `conftest.py` session fixture creates all tables before tests run and drops them after.
- A `.env.test` file (gitignored) or CI environment variable provides the test DB URL. The README must document this.

Example `conftest.py` pattern for PostgreSQL + SQLAlchemy (sync):

```python
import pytest
from sqlalchemy import create_engine, text
from yourapp.db.models import Base
from yourapp.config.settings import get_settings

@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
```

The `DATABASE_URL` in `.env` (or `.env.test`) must point at a real PostgreSQL test database before running tests.
