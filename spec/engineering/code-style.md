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

Python (PEP 8), with project specifics:

- **Modules / packages:** `snake_case` (`graph/nodes.py`, `llm/client.py`, `tools/ingest_dataset.py`). Package name is `data_analyst` (matches the slug `data-analyst` with the hyphen → underscore).
- **Classes:** `PascalCase` — Pydantic domain models (`Dataset`, `QueryResult`, `AuditLogEntry`), SQLAlchemy rows (`SessionRow`, `DatasetRow`, `MessageRow`, `AuditLogRow`), and the `LLMClient` wrapper.
- **Functions / variables:** `snake_case`. Graph node functions are verbs describing the step (`classify_intent`, `generate_sql`, `validate_sql`, `execute_query`, `summarize_result`, `handle_error`, `finalize`).
- **Constants / module-level config:** `UPPER_SNAKE_CASE` (`DEFAULT_SAMPLE_ROWS`, `MAX_SQL_RESULT_ROWS`).
- **Pydantic field names and DB columns:** `snake_case` (`session_id`, `dataset_id`, `executed_sql`, `row_count`).
- **Env vars:** prefixed `DATA_ANALYST_` (`DATA_ANALYST_DATABASE_URL`, `DATA_ANALYST_LLM_MODEL`, `DATA_ANALYST_GEMINI_API_KEY`).
- **Prompt files:** `<name>.md` in `src/data_analyst/prompts/` with node-tag conventions (e.g. `nl_to_sql.md`), loaded at runtime.
- **Tests:** files `test_<thing>.py`; functions `test_<behavior>`.

## File Organization

By **layer**, following `spec/engineering/project-layout.md` exactly. All application code lives under `src/data_analyst/`:

```
src/data_analyst/
├── api/            FastAPI routers (one per resource) + create_app() + _common.py (ok/api_error) + render() helper
├── config/         settings.py (Pydantic BaseSettings, DATA_ANALYST_ prefix, resolved_llm_provider)
├── db/             models.py (SQLAlchemy 2.0 metadata-store rows), session.py (engine + init_db)
├── domain/         Pydantic models per entity (Dataset, QueryResult, AuditLogEntry, ...)
├── graph/          state.py (AgentState TypedDict), nodes.py, edges.py, agent.py (compiled StateGraph), runner.py
├── llm/            client.py (LLMClient), providers/ (base.py, factory.py, gemini.py, stub.py)
├── tools/          pure functions: ingest_dataset.py, run_analytical_sql.py (DuckDB access lives here, not in nodes)
├── prompts/        *.md prompt templates
├── duck/           DuckDB connection/engine helper (analytical store) — kept separate from db/ (the SQLite metadata store)
└── observability/  events.py (structlog config)
tests/              at repo root (NOT under src/): unit/ and integration/
alembic/            migrations for the SQLite metadata store only
```

- One responsibility per file. DuckDB access is confined to `tools/` (and the `duck/` connection helper) — graph nodes call tools, they don't open DuckDB connections themselves.
- No repository pattern: direct SQLAlchemy queries in API handlers / runner against the metadata store; direct DuckDB SQL in tools against the analytical store.
- Graph state is a `TypedDict` (not a dataclass or Pydantic model), per the layout rules.

## Error Handling Pattern

Two boundaries, two patterns:

**1. Pipeline (graph) errors → never raise out of a node.** A node that fails (LLM provider error, invalid generated SQL, DuckDB execution error, timeout) writes a human-readable string into the state's `error` field and returns. Edge functions route to the `handle_error` node, which records the failure (audit log + metadata DB status) and terminates the graph cleanly. **Nodes must never raise `HTTPException`.**

**2. Web routes → render an error template; JSON routes → `api_error()` envelope.**
   - For HTML routes that run the pipeline: when `final_state["error"]` is set, log it and render `error.html` (which always exists and links back to the upload/start page) via the `render()` helper. Do **not** re-raise as `HTTPException`. (See the boilerplate "Pipeline Errors — Render an Error Template" section below — this is binding.)
   - For JSON routes: return the `ok(data)` envelope on success, or raise `api_error(code, message, status_code)` for client/validation errors (bad upload, unknown dataset). Never return a raw dict.

Generated SQL is validated before execution (read-only intent; reject DDL/DML that mutates user data) — a validation failure is a pipeline error routed to `handle_error`, not an exception.

## Logging Pattern

**structlog**, structured (key-value), configured once in `observability/events.py`. Never use bare `print` or unstructured `logging`.

- **Always include where relevant:** `session_id`, `dataset` (id or name), and `sql` (the executed analytical SQL) on any event in the query path. Add `model` and resolved `provider` on LLM events, `row_count` / `duration_ms` on execution events.
- **Event naming:** dotted, lowercase, `area.action` (`analyze.pipeline_error`, `ingest.dataset_loaded`, `sql.executed`, `llm.call`).
- **Never log raw dataset rows or raw cell values** beyond the bounded sample already permitted to the LLM. Logs follow the same local-data-only boundary as the LLM: schema + bounded samples only.
- **Audit log is separate from app logs:** every DuckDB SQL execution and every data operation also writes a persistent `AuditLogEntry` row to the SQLite metadata store (structured logs are for ops; the audit log is the durable record).

## Testing Conventions

- **Runner:** `pytest`. `pyproject.toml` sets `testpaths = ["tests"]`. All commands `uv run pytest ...`.
- **Location:** `tests/` at the **repo root** (never under `src/`), split into `tests/unit/` and `tests/integration/`. `tests/conftest.py` resets the `Settings` singleton between tests (`m._settings = None`).
- **Naming:** files `test_*.py`; functions `test_*`.
- **Same-driver rule (compliant):** tests run against **SQLite**, the production metadata driver — this satisfies the Test Environment Rule because SQLite *is* production here, not a Postgres substitute. Integration tests point the metadata DB at a `tmp_path` SQLite file (not `:memory:`, to avoid cross-test shared state) and create tables via `Base.metadata.create_all`; DuckDB tests use a temp `.duckdb` file. Monkeypatch the session factory and `init_db` per the boilerplate's "Integration Test Patterns".
- **Coverage targets:** unit — smoke (`import data_analyst; assert __version__`), settings resolution (incl. `resolved_llm_provider` and dirty `.env` values with inline comments), domain models, db models, graph compiles with **zero env vars**, and the **stub provider** outputs. Integration — a full stub pipeline run (upload sample CSV → ingest into DuckDB → NL question → generated SQL → executed → one metadata record with `status=completed` → one `AuditLogEntry` written).
- **Phase 2 gate runs with no env vars and no network** (`provider=auto` → stub).

## What NOT to Do

- **Never pass raw dicts across module boundaries.** Use Pydantic domain models and the `ok()` / `api_error()` envelope. (`AgentState` is the one allowed `TypedDict`, for graph state only.)
- **Never send raw dataset rows to the LLM.** Only schema + N sample rows (configurable). Cache dataset schemas so they're computed once. Compute all aggregates in DuckDB and send only the bounded result/summary to the model.
- **Never call the `google-genai` SDK directly inside a graph node or tool.** Go through `LLMClient`, so provider resolution (auto/real/stub), model selection (`gemini-2.5-flash` default, `gemini-2.5-pro` escalation), and token accounting stay centralized.
- **No charts / plotting in v0.1.** Results are HTML tables. Don't add matplotlib/plotly.
- **Never raise `HTTPException` from a graph node.** Pipeline failures flow through the state `error` field and the `handle_error` node; web routes render `error.html`.
- **Don't let generated SQL mutate user data.** Validate for read-only/analytical intent before execution on DuckDB.
- **Don't wrap DuckDB in an ORM** or open DuckDB connections inside nodes — DuckDB access lives in `tools/` / `duck/`.
- **Don't hardcode** the model, sample-row count, result-row cap, ports, or file paths — they come from `Settings` / env (`DATA_ANALYST_` prefix).
- **Don't trust raw `.env` enum values.** Strip inline `#` comments and whitespace in a `resolved_*` property before comparing (`pydantic-settings` does not strip them). Always set `extra="ignore"` on the settings model.
- **Don't silently run in stub mode.** Every page must show a visible stub-mode banner when the resolved provider is `stub`; inject `llm_provider` into every template context.

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
