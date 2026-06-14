# Code Style

> **Boilerplate status:** The tech-designer sub-agent fills in the language-specific sections. General rules below apply to all projects.

---

## Universal Rules

These apply regardless of language or framework:

1. **Types at boundaries** — every function that crosses a module boundary must use typed inputs and outputs (Pydantic, TypeScript interfaces, Go structs, etc.) — never raw dicts or `any`
2. **One responsibility per file** — a file does one thing; if it's doing two things, split it
3. **No comments explaining WHAT** — code should be self-documenting via names; only comment WHY something non-obvious is done
4. **No dead code** — remove unused imports, functions, and variables immediately; don't comment them out
5. **Fail loudly at startup** — validate all required config/env vars at startup; don't fail silently at runtime
6. **No hardcoding** — values that could change (URLs, limits, credentials) go in config or environment variables

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules / files | `snake_case` | `csv_parser.py`, `llm_client.py` |
| Classes | `PascalCase` | `CsvUpload`, `AnalysisSession` |
| Functions / methods | `snake_case` | `parse_csv()`, `run_query()` |
| Variables | `snake_case` | `row_count`, `session_id` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_CSV_ROWS`, `DEFAULT_LLM_MODEL` |
| Pydantic models | `PascalCase` with noun suffix | `QuestionRequest`, `AnswerResponse` |
| FastAPI routers | `snake_case` module, `router` variable | `router = APIRouter()` in `routes/upload.py` |
| SQLAlchemy models | `PascalCase`, singular noun | `Session`, `Upload` |
| Alembic migrations | auto-generated timestamps + short description | `2024_01_15_0001_create_sessions.py` |

All Python code is formatted with **Black** (line length 88, the Black default). Run `uv run black .` before committing. Type hints are required on every function signature that crosses a module boundary — no raw `dict` or `Any` at boundaries; use Pydantic models instead.

## File Organization

Files are grouped **by layer**, following `spec/engineering/project-layout.md`. The application package lives entirely under `src/datachat/`:

```
src/datachat/
  config/
    settings.py         # Pydantic-settings Settings class; resolved_llm_provider property
  db/
    models.py           # SQLAlchemy ORM models
    session.py          # SessionLocal factory; get_db() dependency
    migrations/         # Alembic env.py + versions/
  llm/
    client.py           # get_llm_client() — returns real Gemini or stub based on settings
    stub.py             # StubLlmClient with node-tag-based deterministic responses
    gemini.py           # GeminiClient wrapping google-generativeai
  pipeline/
    analyze.py          # run_pipeline(question, dataframe) → PipelineResult
  routes/
    upload.py           # POST /upload
    query.py            # POST /query
    pages.py            # GET / (index), GET /session/{id}
  static/               # CSS, JS (vanilla, no build)
  templates/            # Jinja2 HTML templates
  main.py               # FastAPI app factory; lifespan; include_router calls
```

One responsibility per file. If a file is doing two things, split it.

## Error Handling Pattern

**API layer (routes):** Never raise `HTTPException` for pipeline or LLM errors — render `error.html` instead (see Pipeline Errors rule in the Framework Gotchas section).

**Pipeline / service layer:** Functions return a typed result object (e.g. `PipelineResult`) that carries either a value or an `error: str | None` field. Do not raise exceptions across layer boundaries for expected failure modes (bad CSV, LLM error, empty result). Raise only for truly unexpected programmer errors.

**LLM errors:** Catch `google.api_core.exceptions.GoogleAPIError` (and subclasses) in `GeminiClient`. Log the exception with `log.error(...)`, then return a structured error string — do not let the raw exception propagate to a route handler.

**Database errors:** Catch `sqlalchemy.exc.SQLAlchemyError` in the DB layer. Log and return a structured error; never expose raw DB error messages to the frontend.

**No bare `except`:** Always name the exception class. `except Exception as e:` is acceptable only at the outermost route handler as a last-resort catch-all, and must always log and return a rendered error page — never swallow.

Structured error responses from JSON endpoints follow this shape:
```json
{ "error": "human-readable description", "detail": "optional technical detail" }
```

## Logging Pattern

Use Python's stdlib `logging` module with structured key=value fields (no third-party logging library in v0.1).

```python
import logging
log = logging.getLogger(__name__)

# Good — key=value fields make log lines greppable
log.error("llm.call_failed", extra={"error": str(e), "node": "analyze", "session_id": sid})

# Bad — unstructured prose
log.error(f"LLM call failed: {e}")
```

Every log record at WARNING or above must include at minimum:
- `session_id` (if available in the current request context)
- the subsystem (`llm`, `db`, `pipeline`, `route`)
- the error/exception string

Log level defaults to `INFO`. Set `DATACHAT_LOG_LEVEL=DEBUG` in `.env` for verbose output.

## Testing Conventions

- **Runner:** `uv run pytest`
- **Test location:** `tests/` at the repo root, mirroring the `src/datachat/` layout (e.g. `tests/pipeline/test_analyze.py`)
- **Naming:** test files prefixed with `test_`, test functions prefixed with `test_`
- **DB in tests:** SQLite in-memory or `tmp_path` file. `conftest.py` creates all tables via `Base.metadata.create_all()` and drops them after. Since production is also SQLite, this satisfies the "same DB as production" rule.
- **LLM in tests:** Always use the stub client. Set `GEMINI_API_KEY` to an empty string (or unset it) in the test environment so `resolved_llm_provider` returns `stub`. Never make real Gemini calls in the test suite.
- **FastAPI routes:** Test with `httpx.AsyncClient` + `ASGITransport` or FastAPI's `TestClient`. Always override `get_db` via `app.dependency_overrides` to inject a test session.
- **No integration tests against live Gemini** in CI. Keep those in a separate `tests/integration/` directory guarded by a `pytest.mark.integration` marker and skipped by default.

## What NOT to Do

- **No `from module import *`** — explicit imports only.
- **No bare `except:`** — always name the exception type.
- **No global mutable state** — no module-level dicts or lists that accumulate state across requests. Pass state through function arguments or FastAPI `Depends()`.
- **No `print()` for logging** — use `logging.getLogger(__name__)`.
- **No direct `os.environ` access in business logic** — read all config from the `Settings` object, injected via `Depends(get_settings)`.
- **No hardcoded model names** outside of `Settings.llm_model` default — every call site reads from settings.
- **No synchronous file I/O inside async route handlers** — use `await anyio.to_thread.run_sync(...)` for blocking file operations, or keep routes sync (FastAPI handles sync routes in a thread pool automatically).
- **No storing raw DataFrames in the DB** — persist only metadata (filename, row count, column names). DataFrames are reconstructed from the uploaded CSV file on demand.
- **No LLM calls in Alembic migration scripts** — migrations must be pure DDL.
- **No inline `# type: ignore` without an explanation comment** explaining why it is unavoidable.

---

## Test Environment Rules

These apply to all projects. No exceptions.

1. **Same DB as production** — if the app uses PostgreSQL, tests use PostgreSQL. SQLite is not a substitute. A test suite that only passes on SQLite tells you nothing about whether migrations and queries work against the real database.

2. **Automated setup — no manual steps** — the `conftest.py` (or equivalent test setup) must create all required tables and tear them down automatically. The test runner must work with a single command (`uv run pytest`, `bun test`, etc.) after setting the test DB URL.

3. **Isolated test database** — use a dedicated database (e.g. `myapp_test`, not `myapp`). Never run tests against the development or production database.

4. **Test DB URL via environment** — expose the test database URL through the same env var mechanism as the app (e.g. `DATABASE_URL` pointing at the test DB, or a `TEST_DATABASE_URL` that the conftest reads). Document this in the README.

5. **DB URL in `.env.example`** — the `.env.example` file must include the test DB URL with a clear placeholder so a new developer knows what to fill in.

6. **`alembic upgrade head` in CI / README** — the README must include `alembic upgrade head` as an explicit step before running the app or tests. Never rely on auto-create from SQLAlchemy metadata alone in production.

---

## Framework Gotchas (keep up to date — known footguns)

### Starlette ≥ 1.0 `TemplateResponse` signature

Starlette 1.0 and FastAPI 0.115+ require the **new** `TemplateResponse` call signature:

```python
# CORRECT (Starlette ≥ 1.0)
return templates.TemplateResponse(request, "page.html", {"foo": bar})

# WRONG (pre-1.0 form) — fails with TypeError: unhashable type: 'dict'
return templates.TemplateResponse("page.html", {"request": request, "foo": bar})
```

A small helper in the routes module keeps call sites tidy:

```python
def render(request: Request, name: str, **ctx):
    return templates.TemplateResponse(request, name, ctx)
```

### LLM provider selection and stubs

Any project with an LLM dependency must follow these patterns:

1. **`provider=auto` by default.** Resolve to the real provider when the API key env var is set, otherwise to the stub. Setting the key is the only step the user should need. Add a `resolved_llm_provider` property on `Settings` that encapsulates this.

2. **Stub outputs branch on explicit node tags, not prose keywords.** Each pipeline node injects a unique tag (`<node:plan>`, `<node:draft>`, `<node:title>`, ...) into its prompt, and the stub matches those tags. Matching on words that also appear in the prompt body cross-contaminates — a draft prompt that contains "expand this outline" must never trigger the stub's "outline" branch.

3. **Stub "draft"-class outputs are article-shaped.** Multiple paragraphs and/or headings — not a bare bullet list. Offline demos must be believable.

4. **The UI shows a visible stub-mode banner** on every page when the resolved provider is `stub`. Inject `llm_provider` into every template context. Silent stubs are a bug.

5. **Tolerate dirty `.env` values.** Config resolution must strip inline `#` comments and surrounding whitespace before comparing enum-like env values (`provider`, `mode`, etc.). A `.env` written months ago with `BLOGFORGE_LLM_PROVIDER=stub   # stub | gemini` must not silently pin the wrong provider. Pydantic-settings does NOT strip inline comments — do it yourself in a `resolved_*` property, never trust the raw field.

---

## Integration Test Patterns

### Replacing an async init function in tests

When your runner calls an async `init_db()` or similar startup function, monkeypatch it with an async noop — not a sync lambda:

```python
# CORRECT
async def _noop(): pass
monkeypatch.setattr("mypackage.agent.runner.init_db", _noop)

# WRONG — breaks await
monkeypatch.setattr("mypackage.agent.runner.init_db", lambda: None)
```

### Replacing the DB session factory in integration tests

```python
@pytest.fixture(autouse=True)
async def _use_test_db(monkeypatch, tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    import mypackage.db.session as s
    monkeypatch.setattr(s, "AsyncSessionLocal", factory)
    monkeypatch.setattr(s, "engine", engine)

    async def _noop(): pass
    monkeypatch.setattr("mypackage.agent.runner.init_db", _noop)
    yield
    await engine.dispose()
```

Use `tmp_path` (not `:memory:`) for integration tests — it avoids shared-state issues across tests.

---

## Pydantic-settings — Always Set `extra="ignore"`

`pydantic-settings` reads **the entire `.env` file** and passes every key to Pydantic for validation. If the `.env` file contains variables the `Settings` model doesn't declare (e.g. `TEST_DATABASE_URL`, `EDITOR`, CI vars), Pydantic will raise:

```
ValidationError: Extra inputs are not permitted [type=extra_forbidden]
```

**Fix:** always set `extra="ignore"` in the `model_config`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APPNAME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # ← required — .env may contain vars we don't own
    )
```

This is mandatory for any project whose `.env` contains variables owned by other tools (test runners, editors, CI, Docker, etc.).

---

## Pipeline Errors — Render an Error Template, Never Raise HTTPException

When an LLM pipeline node fails (provider 4xx/5xx, invalid response, timeout), the failure propagates back to the route via the pipeline state's `error` field.

**Do not** re-raise this as an `HTTPException`:

```python
# WRONG — returns a bare JSON error body to the browser with a 422 status
if state["error"]:
    raise HTTPException(status_code=422, detail=state["error"])
```

**Do** render the error template instead:

```python
# CORRECT — shows the user a readable error page with a "Try again" link
if state["error"]:
    log.error("analyze.pipeline_error", error=state["error"])
    return render(request, "error.html", detail=state["error"])
```

The `error.html` template must always exist and must include a link back to the upload/start page.
Every web route that calls `run_pipeline()` (or equivalent) must follow this pattern.
