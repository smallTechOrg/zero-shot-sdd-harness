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

<!-- FILL IN: Filled in by tech-designer based on language choice. -->

## File Organization

<!-- FILL IN: Filled in by tech-designer. How are files grouped — by layer, by feature, by type? -->

## Error Handling Pattern

<!-- FILL IN: Filled in by tech-designer. How are errors represented and propagated? -->

## Logging Pattern

<!-- FILL IN: Filled in by tech-designer. Structured vs. unstructured? What fields are always included? -->

## Testing Conventions

<!-- FILL IN: Filled in by tech-designer. Unit test location, naming, runner. -->

## What NOT to Do

<!-- FILL IN: Anti-patterns specific to this tech stack. Filled in by tech-designer. -->

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

### Safe code-executing tool pattern (pandas, SQL, shell)

When the agent generates executable code as its action (a pandas expression, SQL query, shell command), the executor **must** use AST validation, not a regex parser:

```python
import ast

_BLOCKED_ATTRS = frozenset({"__class__", "__dict__", "__builtins__", "to_csv", "pipe", ...})
_ALLOWED_NAMES = frozenset({"df", "pd", "True", "False", "None"})

def execute(df, action: str) -> tuple[str, bool]:
    try:
        tree = ast.parse(action, mode="eval")
    except SyntaxError as e:
        return f"SyntaxError: {e}", True

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "Safety error: import not allowed", True
        if isinstance(node, ast.Attribute) and (node.attr.startswith("_") or node.attr in _BLOCKED_ATTRS):
            return f"Safety error: attribute '{node.attr}' not allowed", True
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_NAMES:
            return f"Safety error: name '{node.id}' not in scope", True

    result = eval(compile(tree, "<expr>", "eval"), {"__builtins__": {}, "df": df, "pd": pd})
    return str(result), False
```

**Why not regex?** LLMs generate chained expressions naturally — `df.groupby("region")["sales"].sum()`, `df.sort_values("date").head(10)`, `df["col"].value_counts().nlargest(5)`. A regex that tries to parse call structure will fail on almost every real query and fill the action history with parse errors. The AST approach handles all valid Python without a bespoke parser.

---

### User-friendly agent reasoning trace

The `reasoning_trace` / `action_history` shown to users must be in plain English, not raw code. Structure every plan_action LLM response as:

```
DESCRIPTION: <one sentence a non-technical user can understand>
ACTION: <the executable expression>
```

Store both in each `action_history` entry:
```python
{"description": "Grouping sales by region to find the total for each.", "action": "df.groupby('region')['sales'].sum()", "result": "...", "is_error": False}
```

The golden-path smoke test must assert that `description` is present and non-empty on each trace entry. Showing `df.groupby("region")["sales"].sum()` to a non-technical user is a UX bug — they asked a plain-English question and expect a plain-English explanation of what the agent is doing.

The `force_finalize` summary must also use `description` fields from successful steps, not raw action expressions.

---

### LLM provider selection and stubs

Any project with an LLM dependency must follow these patterns:

1. **`provider=auto` by default.** Resolve to the real provider when the API key env var is set, otherwise to the stub. Setting the key is the only step the user should need. Add a `resolved_llm_provider` property on `Settings` that encapsulates this.

2. **Stub outputs branch on explicit node tags, not prose keywords.** Each pipeline node injects a unique tag (`<node:plan>`, `<node:draft>`, `<node:title>`, ...) into its prompt, and the stub matches those tags. Matching on words that also appear in the prompt body cross-contaminates — a draft prompt that contains "expand this outline" must never trigger the stub's "outline" branch.

3. **Stub "draft"-class outputs are article-shaped.** Multiple paragraphs and/or headings — not a bare bullet list. Offline demos must be believable.

4. **The UI shows a visible stub-mode banner** on every page when the resolved provider is `stub`. Inject `llm_provider` into every template context. Silent stubs are a bug.

5. **Tolerate dirty `.env` values.** Config resolution must strip inline `#` comments and surrounding whitespace before comparing enum-like env values (`provider`, `mode`, etc.). A `.env` written months ago with `BLOGFORGE_LLM_PROVIDER=stub   # stub | gemini` must not silently pin the wrong provider. Pydantic-settings does NOT strip inline comments — do it yourself in a `resolved_*` property, never trust the raw field.

---

## Integration Test Patterns

### Stub-mode detection in tests — use `setenv("KEY", "")` not `delenv`

When a test needs to simulate "no API key set" (stub mode), use `monkeypatch.setenv("MYAPP_API_KEY", "")` instead of `monkeypatch.delenv(...)`.

**Why:** `pydantic-settings` reads from both the process environment and the `.env` file. `delenv` removes the key from the process environment, but pydantic-settings then falls back to the `.env` file, which typically has a placeholder value (`your-api-key-here`). That placeholder is a non-empty string, so `resolved_llm_provider` returns `"gemini"` instead of `"stub"`, and the test fails unexpectedly.

Setting the env var to an empty string overrides the `.env` file value with the empty string, which the `resolved_llm_provider` property correctly treats as stub mode.

```python
# CORRECT — empty string overrides .env placeholder
monkeypatch.setenv("MYAPP_GEMINI_API_KEY", "")

# WRONG — pydantic-settings falls back to .env file value ("your-key-here" → truthy → "gemini")
monkeypatch.delenv("MYAPP_GEMINI_API_KEY", raising=False)
```

---

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
