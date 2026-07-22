# Code Style

> Generic code conventions that apply to **every** project — harness doctrine the code-generator follows,
> not a per-project file. The language-specific sections below are filled in once per project by the
> spec-writer, based on `spec/architecture.md` (`## Stack`).

---

## Universal Rules

These apply regardless of language or framework:

1. **Types at boundaries** — every function that crosses a module boundary must use typed inputs and
   outputs (Pydantic, TypeScript interfaces, Go structs, etc.) — never raw dicts or `any`
2. **One responsibility per file** — a file does one thing; if it's doing two things, split it
3. **No comments explaining WHAT** — code should be self-documenting via names; only comment WHY
   something non-obvious is done
4. **No dead code** — remove unused imports, functions, and variables immediately; don't comment them out
5. **Fail loudly at startup** — validate all required config/env vars at startup; don't fail silently at
   runtime
6. **No hardcoding** — values that could change (URLs, limits, credentials) go in config or environment
   variables

## Naming Conventions

<!-- FILL IN: Filled in by spec-writer based on language choice. -->

## File Organization

<!-- FILL IN: Filled in by spec-writer. How are files grouped — by layer, by feature, by type? -->

## Error Handling Pattern

<!-- FILL IN: Filled in by spec-writer. How are errors represented and propagated? -->

## Logging Pattern

<!-- FILL IN: Filled in by spec-writer. Structured vs. unstructured? What fields are always included? -->

## Testing Conventions

<!-- FILL IN: Filled in by spec-writer. Unit test location, naming, runner. -->

## What NOT to Do

<!-- FILL IN: Anti-patterns specific to this tech stack. Filled in by spec-writer. -->

---

## Test Environment Rules

See `harness/patterns/tech-stack.md` for the full, stack-agnostic test-environment rules (same DB engine
as production, automated setup/teardown, isolated test database, `.env.example` documents every required
variable). Nothing here overrides those; this section exists only to point generators at them from the
code-conventions file too.

---

## Framework Gotchas (project-specific — record known footguns for THIS project's stack here)

<!-- FILL IN: Filled in as the project's actual stack surfaces real footguns. Keep entries dated and
     scoped to the exact framework/version that has the gotcha, so the note doesn't mislead a project on
     a different stack. -->

Below is a worked, fully-illustrative example of the *shape* this section takes for a Python + FastAPI +
Pydantic-settings + LLM-pipeline stack. **Do not apply this content to a project on a different stack —
replace it entirely with that project's own gotchas, or delete it if none are known yet.**

<details>
<summary>Example only — Python/FastAPI illustration, not project doctrine</summary>

### Starlette ≥ 1.0 `TemplateResponse` signature

```python
# CORRECT (Starlette ≥ 1.0)
return templates.TemplateResponse(request, "page.html", {"foo": bar})

# WRONG (pre-1.0 form) — fails with TypeError: unhashable type: 'dict'
return templates.TemplateResponse("page.html", {"request": request, "foo": bar})
```

### Pydantic-settings — always set `extra="ignore"`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APPNAME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # required — .env may contain vars this model doesn't own
    )
```

Without `extra="ignore"`, `pydantic-settings` raises `ValidationError: Extra inputs are not permitted`
the moment `.env` contains any variable the model doesn't declare (test-runner vars, CI vars, editor
vars).

### Pipeline errors — render an error template, never raise a bare HTTP exception

```python
if state["error"]:
    # WRONG: raise HTTPException(status_code=422, detail=state["error"])
    log.error("analyze.pipeline_error", error=state["error"])
    return render(request, "error.html", detail=state["error"])  # readable page + "Try again" link
```

</details>

---

## Integration Test Patterns

Integration and e2e tests call **real** external dependencies with credentials loaded from `.env` (where
the project has any) — never stubbed. The suite is thoroughly tested: edge cases, error paths,
end-to-end journeys, and (for any UI/HTTP surface) UI states are all required. Because real responses can
be non-deterministic, integration/e2e assertions check stable structural properties (status, shape, key
fields) rather than exact prose; unit tests stay fully deterministic (inject the clock, seed randomness).
Run against the production-shaped DB driver, never a lightweight substitute if production uses a real
database engine.

Use whatever this stack's idiomatic pattern is for swapping in an isolated test database and a
noop/async-safe startup hook — the specific mechanics (a fixture, a `beforeEach`, a `conftest.py`) are
recorded per-project above, not hardcoded here.
