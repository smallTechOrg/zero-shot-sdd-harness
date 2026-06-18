# Tech Stack

> **Boilerplate status:** Filled in by the tech-designer sub-agent after the product spec is approved. The user may override specific choices before the tech-designer is invoked.
>
> **Recommended defaults** (override any of these if the project calls for something different):
> - **Backend language:** Python 3.12+ (agent logic, data processing, API server)
> - **Frontend/tooling language:** Node.js 20+ (UI, build tooling, CLI scripts)
> - **Database:** SQLite (zero-ops, file-based, ships with Python — upgrade to PostgreSQL only when multi-user concurrency requires it)

---

## Language

**Backend:** Python 3.12+
**Frontend:** TypeScript 5 / Node.js 20+

**Why:** Python 3.12 is the best fit for the agent and data-processing layer — pandas, LangGraph, and the Google Generative AI SDK all have first-class Python support. TypeScript/Node.js is the standard choice for the browser UI (Vite + React) and ensures type safety end-to-end across the frontend.

## Agent Framework

**LangGraph** (Python)

**Why:** LangGraph models the ReAct loop as an explicit state machine with typed state, conditional edges, and a configurable max-iterations guard — exactly what Rule #9 requires. It runs synchronously inside a FastAPI background task and streams step results via SSE without needing a separate worker process.

## LLM Provider

**Google Gemini** (`google-generativeai` SDK)

**Model:** `gemini-2.5-flash`

**Why:** The user has a Gemini API key and selected Gemini at intake. `gemini-2.5-flash` is the current recommended default for Gemini (see LLM Model Name Rule below — `gemini-2.0-flash` and `gemini-1.5-flash` are unavailable for new users as of 2026). The model name is configurable via `DATA_ANALYST_LLM_MODEL` so it can be changed without a code deployment.

## Backend Framework

**FastAPI** with **uvicorn** (ASGI)

- Port: **8001** (hard-coded in `__main__.py`; overridable via `DATA_ANALYST_PORT`)
- File uploads handled via `python-multipart`
- Streaming responses via Server-Sent Events (SSE) — `starlette.responses.StreamingResponse`
- Lifespan context manager initialises DB and loads settings at startup

## Database

**SQLite** — file-based, zero configuration, ships with Python's stdlib.

Used for: run metadata (status, file path, timestamps, token usage) and chat history (user messages + agent answers per session).

**ORM:** SQLAlchemy 2.0 with `Mapped` / `mapped_column` declarative syntax (synchronous engine — SQLite does not benefit from async I/O).

Upgrade path: swap `sqlite:///` URL for `postgresql+psycopg2://` and re-run `alembic upgrade head` — no other code changes required.

## Frontend

**Vite 5 + React 18 + TypeScript 5**

- Package manager: **pnpm**
- Build output served as static files by FastAPI in production (`StaticFiles` mount)
- In development: Vite dev server on port 5173 proxies `/api/*` to FastAPI on 8001
- UI components: plain React — no UI library dependency in v0.1 to keep the bundle lean

## Key Libraries

### Python (backend)

| Library | Version | Purpose |
|---------|---------|---------|
| fastapi | ≥0.115 | HTTP API server, routing, dependency injection |
| uvicorn | ≥0.30 | ASGI server (production and dev) |
| langgraph | ≥0.2 | ReAct loop state-machine graph |
| google-generativeai | ≥0.8 | Gemini LLM client |
| pandas | ≥2.2 | In-memory DataFrame — data loading and analysis |
| sqlalchemy | ≥2.0 | ORM for SQLite (Mapped types) |
| alembic | ≥1.13 | Database migrations |
| pydantic-settings | ≥2.0 | Config from env vars / .env file |
| python-multipart | ≥0.0.9 | File upload parsing (required by FastAPI) |
| structlog | ≥24.0 | Structured (JSON) logging bound to run_id |
| pytest | ≥8.0 | Test runner |
| httpx | ≥0.27 | AsyncClient for FastAPI TestClient in tests |

### Node.js (frontend)

| Library | Version | Purpose |
|---------|---------|---------|
| react | 18 | UI component framework |
| react-dom | 18 | DOM rendering |
| typescript | 5 | Static types |
| vite | 5 | Build tool and dev server |
| @vitejs/plugin-react | ≥4 | Vite React transform |

## What to Avoid

| Pattern | Reason |
|---------|--------|
| `eval()` or `exec()` on raw LLM output | Security — untrusted code execution. Use the pandas allowlist validator instead. |
| Direct pandas writes in agent actions (`df.to_sql`, `df.to_csv`, `df.to_parquet`) | Agent actions must be read-only; writes mutate state outside the sandbox. |
| `asyncpg` or `aiosqlite` | SQLite with a synchronous engine is sufficient; async DB adds complexity without benefit here. |
| Global mutable DataFrame state without a keyed store | Each session/run must have its own DataFrame keyed by `session_id` to prevent cross-session data leaks. |
| Importing pandas in the frontend bundle | pandas is Python-only; any data shaping for the UI must happen in the API layer. |
| Hardcoded model names | Always read from `DATA_ANALYST_LLM_MODEL` env var — model names change. |
| `pip install` instead of `uv` | All Python dependency operations must use `uv` for reproducibility. |
| `npm` or `yarn` for frontend | Use `pnpm` exclusively. |
| Bare `alembic` / `pytest` / `python` commands in docs | Always prefix with `uv run` — bare commands fail when the venv is not activated. |

## Dependency Management

**Python:** `uv` + `pyproject.toml`
- All runtime deps in `[project.dependencies]`
- Dev/test deps in `[dependency-groups.dev]`
- Lock file: `uv.lock` (committed to version control)
- SQLite driver ships with Python stdlib — no extra driver package needed

**Node.js:** `pnpm` + `package.json`
- Lock file: `pnpm-lock.yaml` (committed to version control)
- Frontend source lives in `src/frontend/` (see project-layout.md)

---

## Permanent Rules (apply to all projects, not filled in by tech-designer)

### Recommended Default Stack

When the user states no preference, the **recommended default stack** is:

- **Backend / agent:** Python 3.12+
- **Frontend:** Node.js (TypeScript / Next.js)
- **Database:** SQLite

This is the stack the intake question (`agent-builder` Q2) recommends first. The user may override any part of it by choosing another option — their stated preference is always binding (see `.claude/agents/tech-designer.md` § "User Preferences Are Binding").

**The frontend is always Node.js, never Python.** Any UI/web surface is built in Node.js (TypeScript/Next.js) regardless of the backend language. There is no Python frontend option. Python is for the backend/agent only.

### Default Dev Port

All generated projects **must** use **port 8001** as the default development port (not 8000).

Reason: Port 8000 is commonly occupied by other local services (other FastAPI apps, Django, http.server, etc.). Using 8001 avoids startup failures with no code change needed.

- `__main__.py` must hard-code `port=8001` (not 8000) unless overridden by an env var
- README must reference `http://localhost:8001`
- `.env.example` should include `PORT=8001` if the port is configurable

### LLM Model Name Rule

**Always use a current, verified model name — never a deprecated or guessed one.**

- For Google Gemini: use **`gemini-2.5-flash`** as the default (not `gemini-2.0-flash` or `gemini-1.5-flash` — both unavailable for new users).
- Model names change. Before hardcoding any model identifier, verify it exists by calling the provider's `ListModels` API or checking current documentation.
- The model name must be configurable via an env var (e.g. `DATA_ANALYST_LLM_MODEL`) so it can be changed without a code deployment.
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

**Tests must use the same database driver as production.** This project uses SQLite in both production and tests — no substitution needed.

- Tests use a temporary SQLite file via `tmp_path` (not `:memory:`) to avoid shared-state issues.
- `conftest.py` creates and tears down the test database automatically.
- The test database URL is provided by `monkeypatch` in `conftest.py` — no manual step.

### Phase Gate Commands

| Phase | Gate command | What it checks |
|-------|-------------|----------------|
| 1 | `uv run pytest tests/unit/ -v` | Domain models, settings, graph compiles, DB models |
| 2 | `uv run pytest tests/ -v` | Full suite — unit + integration (stub LLM, real SQLite) |

All commands run from the **repo root**.
