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

### Python (backend)

| Element | Convention | Example |
|---------|-----------|---------|
| Packages and modules | `snake_case` | `data_analyst`, `graph/nodes.py` |
| Functions and methods | `snake_case` | `plan_action()`, `execute_action()` |
| Classes | `PascalCase` | `AgentState`, `RunRow`, `DatasetRow` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_AGENT_ITERATIONS`, `SAFE_PANDAS_METHODS` |
| Type aliases | `PascalCase` | `ActionHistory`, `DataFrameStore` |
| Private helpers | leading underscore | `_validate_action()`, `_build_prompt()` |
| Node functions | verb + noun, no prefix | `setup()`, `plan_action()`, `execute_action()`, `finalize()` |
| Edge functions | `after_<node_name>` | `after_plan_action()`, `after_execute_action()` |
| Pydantic response models | noun + `Response` / `Request` | `ChatResponse`, `UploadResponse` |
| DB model rows | noun + `Row` | `RunRow`, `DatasetRow`, `MessageRow` |
| Settings fields | `snake_case`, no prefix | `database_url`, `llm_model`, `gemini_api_key` |
| Env var prefix | `DATA_ANALYST_` | `DATA_ANALYST_DATABASE_URL` |

### TypeScript / React (frontend)

| Element | Convention | Example |
|---------|-----------|---------|
| Components | `PascalCase` | `ChatPanel`, `FileUpload`, `StepTrace` |
| Component files | `PascalCase.tsx` | `ChatPanel.tsx` |
| Hooks | `use` + noun | `useChat`, `useUpload` |
| Utility functions | `camelCase` | `formatCost`, `parseSSEChunk` |
| Types and interfaces | `PascalCase` | `ChatMessage`, `StepEvent`, `UploadResult` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_FILE_SIZE_MB` |
| CSS module classes | `camelCase` | `chatPanel`, `uploadArea` |

## File Organization

### Python backend

Files are grouped **by layer** (not by feature), matching the canonical project layout:

```
src/data_analyst/
├── api/            ← FastAPI routers — one file per domain resource
│   ├── __init__.py       (create_app factory + lifespan)
│   ├── _common.py        (ok(), api_error(), stream helpers)
│   ├── health.py
│   ├── datasets.py       (upload, list, delete)
│   └── chat.py           (ask question, stream SSE)
├── config/
│   └── settings.py       (pydantic-settings, one Settings class)
├── db/
│   ├── models.py         (SQLAlchemy Mapped models — RunRow, DatasetRow, MessageRow)
│   └── session.py        (engine, sessionmaker, get_session, init_db)
├── domain/
│   ├── dataset.py        (Dataset, UploadResult Pydantic models)
│   └── chat.py           (ChatRequest, ChatResponse, StepEvent Pydantic models)
├── graph/
│   ├── state.py          (AgentState TypedDict)
│   ├── nodes.py          (setup, plan_action, execute_action, finalize, force_finalize, handle_error)
│   ├── edges.py          (after_setup, after_plan_action, after_execute_action)
│   ├── agent.py          (StateGraph compiled once at startup)
│   └── runner.py         (run_agent() entry point, SSE generator)
├── llm/
│   ├── client.py         (LLMClient wrapper around google-generativeai)
│   └── providers/
│       ├── base.py       (abstract LLMProvider protocol)
│       ├── factory.py    (create_llm_client())
│       ├── gemini.py     (real Gemini provider)
│       └── stub.py       (offline stub, returns tagged outputs)
├── tools/
│   └── pandas_executor.py  (validate_action, execute_action — pure functions)
├── prompts/
│   ├── plan_action.md    (system prompt for the plan_action node)
│   └── force_finalize.md (system prompt for force_finalize)
└── observability/
    └── events.py         (structlog configuration, bound context factory)
```

### TypeScript frontend

```
src/frontend/
├── src/
│   ├── components/       (shared UI components)
│   ├── pages/            (top-level route views)
│   ├── hooks/            (custom React hooks)
│   ├── api/              (typed fetch wrappers for backend endpoints)
│   ├── types/            (shared TypeScript interfaces)
│   └── main.tsx          (app entry point)
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

**Rule:** no component imports from `api/` directly — all backend calls go through a hook (`useChat`, `useUpload`) that owns loading and error state.

## Error Handling Pattern

### Python — three tiers

1. **Fatal (graph-level):** LLM API is unreachable, uploaded file is missing from disk, session state is corrupt. Set `state["error"]` and route to `handle_error`. The node does not raise — it returns the updated state. `handle_error` persists the failure and terminates the graph.

2. **Recoverable (loop-level):** A pandas operation raises an exception (bad column name, type error, out-of-bounds). Catch the exception in `execute_action`, set `is_error: True` on the appended history entry, and route back to `plan_action`. The LLM sees the error inline and can retry.

3. **Validation failure (pre-execution):** The LLM output does not match the pandas allowlist. Append as an `is_error: True` history entry with a clear message ("Action not permitted: <operation>") and route back to `plan_action`. Do not execute the rejected action.

```python
# Pattern for execute_action node
try:
    result = validated_executor(action_str, dataframe)
    is_error = False
except ValueError as e:
    result = f"Validation error: {e}"
    is_error = True
except Exception as e:
    result = f"Execution error: {type(e).__name__}: {e}"
    is_error = True
```

### FastAPI routes

- Routes never raise `HTTPException` for agent pipeline failures — render a structured error response with `api_error()` instead.
- `api_error(code, message, status_code)` returns a consistent envelope: `{"data": null, "error": {"code": "...", "message": "..."}}`.
- Validation errors (missing fields, bad file type) raise `api_error` immediately — before invoking the agent.

### TypeScript frontend

- Every API call is wrapped in a hook that exposes `{ data, loading, error }`.
- Errors display inline next to the relevant UI element — never `alert()` or `console.error()` only.
- SSE stream errors (network drop, server close) trigger a user-visible "Connection lost — reload to retry" message.

## Logging Pattern

**Backend:** `structlog` in JSON mode (structured logging).

Every log call must include `run_id` and `session_id` from the bound context:

```python
import structlog

log = structlog.get_logger()

# In nodes — bind run_id once, carry it through
bound_log = log.bind(run_id=state["run_id"], session_id=state["session_id"])
bound_log.info("plan_action.start", iteration=state["iteration_count"])
bound_log.info("execute_action.result", action=action_str, is_error=is_error)
bound_log.error("handle_error", error=state["error"])
```

Mandatory fields on every log event:

| Field | Source |
|-------|--------|
| `run_id` | `AgentState.run_id` |
| `session_id` | `AgentState.session_id` |
| `event` | string — `"<node>.<action>"` (e.g. `"plan_action.llm_call"`) |
| `level` | info / warning / error |

Optional but expected in loop nodes:

| Field | When |
|-------|------|
| `iteration` | every `plan_action` and `execute_action` call |
| `tokens_input` / `tokens_output` | after each LLM call |
| `action` | in `execute_action` — what was attempted |
| `is_error` | in `execute_action` — whether execution succeeded |

**Log level defaults:**

| Level | When |
|-------|------|
| `INFO` | normal operation (node start/end, LLM call, action result) |
| `WARNING` | recoverable error (pandas exception, invalid action, near max iterations) |
| `ERROR` | fatal failure routed to `handle_error` |

**Frontend:** no `console.log` in production builds. Use a minimal structured logger (`{ level, message, context }`) that is a no-op when `import.meta.env.PROD` is true.

## Testing Conventions

### Runner and structure

- **Runner:** `uv run pytest tests/ -v`
- **Test root:** `tests/` at the repo root (not inside `src/`)
- **Phase 1 gate:** `uv run pytest tests/unit/ -v`
- **Phase 2 gate:** `uv run pytest tests/ -v`

### File naming

| Test file | What it covers |
|-----------|---------------|
| `tests/unit/test_smoke.py` | `import data_analyst; assert __version__ == "0.1.0"` |
| `tests/unit/config/test_settings.py` | Settings loads from env; env prefix enforced |
| `tests/unit/db/test_models.py` | SQLAlchemy models have correct columns |
| `tests/unit/domain/test_models.py` | Pydantic domain models validate correctly |
| `tests/unit/graph/test_agent.py` | Graph compiles without env vars; no import errors |
| `tests/unit/tools/test_pandas_executor.py` | Allowlist enforcement; safe ops execute; unsafe ops rejected |
| `tests/integration/test_pipeline.py` | Stub run completes; one DB record; status=completed |
| `tests/integration/test_api.py` | HTTP upload + chat endpoints return correct envelopes |

### Fixtures and isolation

- Every test that touches the DB uses a `tmp_path`-based SQLite fixture (not `:memory:`) via `conftest.py`.
- The settings singleton (`_settings`) is reset via `autouse` fixture in `conftest.py` so `monkeypatch.setenv` takes effect.
- LLM calls are stubbed in all unit and integration tests — no API key required for `uv run pytest tests/ -v`.
- Stub outputs use tagged prompts (`<node:plan_action>`, `<node:force_finalize>`) so node stubs never cross-contaminate.

### Frontend tests

- Unit tests: Vitest + React Testing Library for components and hooks.
- E2E: Playwright for the full browser journey (upload CSV → ask question → see step trace → see final answer).
- E2E tests run against a local dev server with the backend stub provider active.

## What NOT to Do

| Anti-pattern | Correct approach |
|--------------|-----------------|
| `eval(llm_output)` | Validate against pandas allowlist, then call the method directly |
| `exec(llm_output)` | Same — never execute raw model strings |
| Direct `df.to_sql()` / `df.to_csv()` in agent actions | Read-only operations only; enforce via allowlist |
| Storing a DataFrame in `AgentState` directly | Store a `dataframe_key` string; DataFrame lives in module-level dict keyed by `session_id` |
| `git add -A` | Stage specific files or directories only |
| Bare `pytest` / `alembic` / `python` in docs | Always prefix with `uv run` |
| Sharing a global DataFrame across sessions | Each session gets its own keyed slot in the module-level store |
| `any` type in TypeScript | Define a typed interface; use `unknown` + type guard if truly unknown |
| Silent stub (no UI banner) | Show a visible "Offline / stub mode" banner when `gemini_api_key` is not set |
| One-shot pipeline for data Q&A | ReAct loop — mandatory per Rule #9 |
| Raising `HTTPException` inside the agent pipeline | Set `state["error"]` and route to `handle_error`; the API layer reads the final state |
| Inline `#` comments in `.env` values | Strip trailing comments in `resolved_*` properties on `Settings` |

---

## Test Environment Rules

See `spec/engineering/tech-stack.md` § "Test Environment Rule" (canonical) — same DB driver as production, automated `conftest.py` setup, isolated test DB, URL via env, `alembic upgrade head` documented.

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

2. **Stub outputs branch on explicit node tags, not prose keywords.** Each pipeline node injects a unique tag (`<node:plan_action>`, `<node:force_finalize>`) into its prompt, and the stub matches those tags. Matching on words that also appear in the prompt body cross-contaminates — a draft prompt that contains "expand this outline" must never trigger the stub's "outline" branch.

3. **Stub "draft"-class outputs are article-shaped.** Multiple paragraphs and/or headings — not a bare bullet list. Offline demos must be believable.

4. **The UI shows a visible stub-mode banner** on every page when the resolved provider is `stub`. Inject `llm_provider` into every template context. Silent stubs are a bug.

5. **Tolerate dirty `.env` values.** Config resolution must strip inline `#` comments and surrounding whitespace before comparing enum-like env values (`provider`, `mode`, etc.). A `.env` written months ago with `DATA_ANALYST_LLM_PROVIDER=stub   # stub | gemini` must not silently pin the wrong provider. Pydantic-settings does NOT strip inline comments — do it yourself in a `resolved_*` property, never trust the raw field.

### pandas allowlist executor

The `tools/pandas_executor.py` module is the only place where DataFrame operations are executed. It must:

1. Parse the LLM action string into an operation name and arguments (regex or simple split — not `eval`).
2. Check the operation name against `SAFE_PANDAS_METHODS` (a module-level frozenset).
3. Call the method via `getattr(df, method_name)(*args, **kwargs)` — not `eval`.
4. Return the result as JSON-serialisable data: first 20 rows as a list of dicts for DataFrames, scalar value otherwise.
5. Raise `ValueError` (not `RuntimeError`) for allowlist violations — this signals a recoverable loop error, not a fatal crash.

```python
SAFE_PANDAS_METHODS: frozenset[str] = frozenset({
    "head", "tail", "describe", "info", "shape", "dtypes",
    "columns", "index", "value_counts", "nunique", "unique",
    "groupby", "agg", "mean", "median", "std", "sum", "min", "max",
    "corr", "sort_values", "nlargest", "nsmallest", "filter",
    "query", "loc", "iloc", "select_dtypes", "count", "isnull",
    "notnull", "dropna", "fillna", "rename", "reset_index",
    "set_index", "pivot_table", "crosstab", "merge", "concat",
    "sample", "idxmin", "idxmax",
})
```

Never add write methods (`to_sql`, `to_csv`, `to_parquet`, `drop`, `insert`, `update`, `delete`, `assign` with mutation) to this set.

### SSE streaming from FastAPI

Use `StreamingResponse` with `media_type="text/event-stream"` and `Cache-Control: no-cache`. Each SSE event must be a complete `data: <json>\n\n` chunk. The frontend `EventSource` must handle reconnection on drop.

```python
# CORRECT
async def event_generator():
    for step in run_agent_steps(state):
        yield f"data: {json.dumps(step)}\n\n"
    yield "data: [DONE]\n\n"

return StreamingResponse(event_generator(), media_type="text/event-stream",
                         headers={"Cache-Control": "no-cache"})
```

---

## Integration Test Patterns

### Replacing an async init function in tests

When your runner calls an async `init_db()` or similar startup function, monkeypatch it with an async noop — not a sync lambda:

```python
# CORRECT
async def _noop(): pass
monkeypatch.setattr("data_analyst.graph.runner.init_db", _noop)

# WRONG — breaks await
monkeypatch.setattr("data_analyst.graph.runner.init_db", lambda: None)
```

### Replacing the DB session factory in integration tests

```python
@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch, tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    import data_analyst.db.session as s
    monkeypatch.setattr(s, "_engine", engine)
    monkeypatch.setattr(s, "_SessionLocal", factory)
    monkeypatch.setattr(s, "init_db", lambda: None)
    yield
    engine.dispose()
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
        env_prefix="DATA_ANALYST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # ← required — .env may contain vars we don't own
    )
```

This is mandatory for any project whose `.env` contains variables owned by other tools (test runners, editors, CI, Docker, etc.).

---

## Pipeline Errors — Return a Structured Error Response, Never Raise HTTPException

When an LLM pipeline node fails (provider 4xx/5xx, invalid response, timeout), the failure propagates back to the route via `state["error"]`.

**Do not** re-raise this as an `HTTPException`:

```python
# WRONG — returns a bare JSON error body to the browser with a 422 status
if state["error"]:
    raise HTTPException(status_code=422, detail=state["error"])
```

**Do** return a structured error response via `api_error()`:

```python
# CORRECT — returns a consistent error envelope the frontend can handle
if state.get("error"):
    log.error("chat.pipeline_error", error=state["error"])
    return api_error("PIPELINE_ERROR", state["error"], status_code=500)
```

For SSE streams: emit a final `data: {"type": "error", "message": "..."}` event before closing the generator so the frontend can display a user-friendly message.
