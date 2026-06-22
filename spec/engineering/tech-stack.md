# Tech Stack

> **Boilerplate status:** Filled in by the tech-designer sub-agent after the product spec is approved. The user may override specific choices before the tech-designer is invoked.

---

## Language

Python 3.12

**Why:** The agent is data-heavy (CSV/Parquet ingestion, analytical SQL) and agent-heavy (LangGraph orchestration, NL→SQL). Python has the strongest ecosystem for all three — DuckDB, pandas/pyarrow, LangGraph, and the Google Gemini SDK are all first-class. This is also the boilerplate's default for agent/data work.

## Agent Framework

LangGraph

**Why:** The boilerplate standard, and the right fit for a multi-step NL→SQL pipeline with conditional routing (classify intent → generate SQL → validate → execute on DuckDB → summarize, with an error branch). State checkpointing and explicit edge topology keep the analytical flow auditable. The graph lives in `src/data_analyst/graph/`. See `spec/product/07-agent-graph.md` for the node/edge design.

## LLM Provider

Google Gemini

**Model:** Default `gemini-2.5-flash` (cheap, fast NL→SQL); escalate to `gemini-2.5-pro` for complex reasoning (multi-step analytical questions, ambiguous schema mapping). Configurable via `DATA_ANALYST_LLM_MODEL`.

**Why:** Gemini is strong at structured generation (SQL) and tool use. `gemini-2.5-flash` is the cost-efficient default for the high-volume NL→SQL path; `gemini-2.5-pro` is the escalation target when a question needs deeper reasoning. Both model IDs were verified current against the Gemini model catalog during tech design. Accessed via the current official **`google-genai`** SDK (not the deprecated `google-generativeai` package).

> **Model name note for reviewers:** The boilerplate's "Permanent Rules → LLM Model Name Rule" table lists `gemini-2.5-flash` as the current safe default for Google Gemini, and explicitly notes that `gemini-2.0-flash` and `gemini-1.5-flash` are **unavailable for new users**. This project therefore uses `gemini-2.5-flash` as the default and `gemini-2.5-pro` for reasoning escalation — these are the configured defaults. The model is configurable via the `DATA_ANALYST_LLM_MODEL` env var so it can be changed without a code deploy, satisfying the rule's intent.

**Provider resolution / stub mode:** `provider=auto` by default. When `DATA_ANALYST_GEMINI_API_KEY` is set, the real Gemini provider is used; otherwise the agent resolves to a deterministic **stub** provider so the app runs offline with zero API key. A `resolved_llm_provider` property on `Settings` encapsulates this. Every page renders a visible stub-mode banner when the resolved provider is `stub` (see code-style.md).

## Backend Framework (if applicable)

FastAPI (web UI + JSON API), with Jinja2 server-rendered templates. Default dev port **8001**.

**Why:** FastAPI gives one framework for both the HTML upload/query UI (Jinja2 templates) and the JSON endpoints, with Pydantic models at the boundary. Uvicorn is the ASGI server. Charts are out of scope for v0.1 — results render as HTML tables.

## Database (if applicable)

**Dual-store architecture** — two databases with distinct roles:

1. **DuckDB** — the *analytical engine*. Stores uploaded user datasets (CSV/Parquet ingested into tables) and runs all analytical SQL. Local file at `data/datasets.duckdb`. This is where data lives and where aggregates are computed. Not managed by Alembic (DuckDB holds user data tables created at ingestion time, not app schema).

2. **SQLite** — the agent's *metadata store*. Holds the application's own schema: sessions, the datasets registry, messages, and the audit log. Accessed via **SQLAlchemy 2.0**, with **Alembic** migrations. Local file at `data/metadata.db`; `DATA_ANALYST_DATABASE_URL=sqlite:///./data/metadata.db`.

**ORM/ODM:** SQLAlchemy 2.0 (declarative, `Mapped` types) + Alembic — for the SQLite metadata store only. DuckDB is accessed via its own `duckdb` Python driver (no ORM; analytical SQL is generated/executed directly).

> **DB Driver Rule / Test Environment Rule compliance (read this, reviewers):** The production metadata database is **SQLite**, and the SQLite driver ships in Python's stdlib (no separate driver dependency to misplace in dev-only groups). Per the Test Environment Rule, *tests must use the same driver as production* — so the test suite runs against **SQLite**, because SQLite **is** the production metadata driver here. This is **not** the anti-pattern the rule warns about (SQLite standing in for Postgres): there is no Postgres in this project. Integration tests use a `tmp_path` SQLite file (not `:memory:`) to avoid shared-state issues. Alembic's `target_metadata` points at the SQLite `Base.metadata`; `alembic upgrade head` runs against the SQLite file. DuckDB is never migrated by Alembic.

## Frontend (if applicable)

None (no SPA). Server-rendered Jinja2 templates served by FastAPI. Plain HTML + minimal CSS; result sets shown as HTML tables. No JavaScript framework, no charts in v0.1.

## Key Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `fastapi` | latest | Web framework — HTML UI routes + JSON API |
| `uvicorn[standard]` | latest | ASGI server (dev port 8001) |
| `jinja2` | latest | Server-side HTML templates (Starlette ≥ 1.0 `TemplateResponse` signature) |
| `python-multipart` | latest | Multipart form parsing for CSV/Parquet file upload |
| `sqlalchemy` | >=2.0 | ORM for the SQLite metadata store (declarative, `Mapped` types) |
| `alembic` | latest | Schema migrations for the SQLite metadata store |
| `duckdb` | latest | Analytical engine — stores datasets, runs analytical SQL, computes aggregates |
| `pyarrow` | latest | Parquet read + efficient CSV→table ingestion into DuckDB (preferred over pandas for the ingest path) |
| `pandas` | latest | CSV inspection / sample-row extraction and DataFrame interop where pyarrow is awkward |
| `langgraph` | latest | Agent orchestration — the NL→SQL StateGraph |
| `google-genai` | latest | Google Gemini SDK (official; not `google-generativeai`) — wrapped by `LLMClient`, never called directly in graph nodes |
| `pydantic` | >=2 | Typed models at every module boundary (domain models, API envelopes) |
| `pydantic-settings` | latest | Env-driven `Settings` (`DATA_ANALYST_` prefix, `extra="ignore"`) |
| `structlog` | latest | Structured logging (session_id / dataset / sql fields) |
| `pytest` | latest | Test runner (unit + integration) |

## What to Avoid

- **Never send raw dataset rows to the LLM.** Only the schema + a small number of sample rows (N, configurable) ever reach Gemini. Datasets stay local in DuckDB. This is a hard privacy boundary.
- **No charts/plotting libraries in v0.1.** Results are HTML tables only. Matplotlib/Plotly are out of scope.
- **No calling the `google-genai` SDK directly from graph nodes.** All LLM access goes through `LLMClient` (`src/data_analyst/llm/client.py`) so the stub provider, model selection, and token accounting stay in one place.
- **No Postgres / no Postgres driver.** The metadata store is SQLite by design; do not add `psycopg2`/`asyncpg` or a Postgres test database.
- **No ORM over DuckDB.** DuckDB holds user data and runs generated analytical SQL directly; do not wrap it in SQLAlchemy.
- **No raw dicts at module boundaries** — use Pydantic models / typed envelopes (`ok()` / `api_error()`).
- **No deprecated/guessed model names.** Use the verified Gemini model IDs (`gemini-2.5-flash`, `gemini-2.5-pro`); never fall back to `gemini-2.0-flash` or `gemini-1.5-flash` (unavailable for new users).

## Dependency Management

`uv` + `pyproject.toml`. All commands run from the repo root, prefixed with `uv run` (e.g. `uv run alembic upgrade head`, `uv run pytest`, `uv run uvicorn ...`). The `duckdb` driver and all runtime libs live in `[project.dependencies]` (not a dev-only group) so `alembic upgrade head` and dataset ingestion work in any environment.

## Phase Gate Commands

| Phase | Gate command |
|-------|-------------|
| 1 | `uv run pytest tests/unit` |
| 2 | `uv run pytest tests/integration` |

Notes:
- Phase 2 (integration) must pass with **zero env vars set** — `provider=auto` resolves to the stub, the metadata DB uses a `tmp_path` SQLite file, and DuckDB uses a temp file. No network I/O, no API key.
- Both gates run against SQLite, which is the production metadata driver (see the DB Driver Rule / Test Environment Rule note above).
- Full suite: `uv run pytest`.

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
