# Code Style

Filled in by the researcher/planner. Universal rules apply to all projects; stack-specific
sections are filled in per-project.

---

## Universal Rules

1. **Types at boundaries** — every function crossing a module boundary uses typed inputs/outputs; never raw dicts or `any`
2. **One responsibility per file** — if a file does two things, split it
3. **No comments explaining WHAT** — only comment WHY something non-obvious is done
4. **No dead code** — remove unused imports, functions, variables immediately
5. **Fail loudly at startup** — validate all required config/env vars at startup; never fail silently at runtime
6. **No hardcoding** — values that could change (URLs, limits, credentials) go in config/env vars

## Naming Conventions

<!-- FILL IN: language-specific conventions -->

## File Organisation

<!-- FILL IN: by layer / by feature / by type? -->

## Error Handling Pattern

<!-- FILL IN: how errors are represented and propagated -->

## Logging Pattern

<!-- FILL IN: structured vs unstructured, always-present fields -->

## Testing Conventions

<!-- FILL IN: unit test location, naming, runner, coverage threshold -->

## What NOT to Do

<!-- FILL IN: anti-patterns specific to this stack -->

---

## Test Environment Rules

1. **Same DB as production** — SQLite is not a substitute for PostgreSQL. Tests that only pass on SQLite are not a passing gate.
2. **Automated setup** — `conftest.py` (or equivalent) creates and tears down all tables. Single command to run tests after setting DB URL.
3. **Isolated test database** — dedicated DB (e.g. `myapp_test`); never run against dev or production.
4. **Test DB URL via environment** — same env var mechanism as the app; documented in README and `.env.example`.
5. **`alembic upgrade head` explicit in README** — never rely on SQLAlchemy auto-create in production.

---

## Python / FastAPI Gotchas

### Starlette ≥ 1.0 `TemplateResponse` signature

```python
# CORRECT (Starlette ≥ 1.0 / FastAPI 0.115+)
return templates.TemplateResponse(request, "page.html", {"foo": bar})

# WRONG — fails with TypeError: unhashable type: 'dict'
return templates.TemplateResponse("page.html", {"request": request, "foo": bar})
```

Use a thin helper to keep call sites tidy:
```python
def render(request: Request, name: str, **ctx):
    return templates.TemplateResponse(request, name, ctx)
```

### pydantic-settings — always `extra="ignore"`

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APPNAME_",
        env_file=".env",
        extra="ignore",   # .env may contain vars we don't own (CI, editor, test runner)
    )
```

### Strip dirty `.env` values

Pydantic-settings does NOT strip inline `#` comments. `PROVIDER=stub  # stub | gemini`
silently pins the wrong provider. Strip in a `resolved_*` property:

```python
@property
def resolved_llm_provider(self) -> str:
    return self.llm_provider.split("#")[0].strip()
```

### Pipeline errors — render template, not HTTPException

```python
# WRONG — returns bare JSON error with 422 status
if state["error"]:
    raise HTTPException(status_code=422, detail=state["error"])

# CORRECT — shows a readable error page with a "Try again" link
if state["error"]:
    log.error("pipeline_error", error=state["error"])
    return render(request, "error.html", detail=state["error"])
```

`error.html` must always exist with a link back to the start page.

### Async monkeypatching in tests

```python
# CORRECT — async noop, not a sync lambda
async def _noop(): pass
monkeypatch.setattr("mypackage.agent.runner.init_db", _noop)
```

### Integration test DB fixture

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
    async def _noop(): pass
    monkeypatch.setattr("mypackage.agent.runner.init_db", _noop)
    yield
    await engine.dispose()
```

Use `tmp_path` (not `:memory:`) — avoids shared-state issues across tests.
