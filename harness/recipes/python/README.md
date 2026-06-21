# Python Recipe

Starter scaffold for a Python + FastAPI + LangGraph + PostgreSQL agent.
The executor copies this into `src/`, `tests/`, and the project root, then
adapts it to the spec. Delete this directory after copying.

---

## What's here

```
pyproject.toml          uv project — deps, pytest config, ruff
alembic.ini             alembic config (URL set from config, not here)
alembic/env.py          async alembic env
alembic/script.py.mako  migration template

src/
  config.py             pydantic-settings — APPNAME_ prefix, SecretStr, stub flag
  __main__.py           uvicorn entry point — port 8001
  api/
    app.py              FastAPI app factory + lifespan + CORS
    health.py           GET /health — returns env, provider, stub_mode
  db/
    base.py             DeclarativeBase
    session.py          async engine + AsyncSessionLocal + init_db()
  agent/
    state.py            AgentState TypedDict — run_id, input, history, result, error
    graph.py            LangGraph graph — plan_action → invoke_tool ↺ → finalize/error
    nodes.py            plan_action, invoke_tool, finalize, handle_error
    tools.py            Tool dataclass + TOOL_REGISTRY + register()
  integrations/
    llm.py              thin LLM client — routes to provider or stub
    stubs/
      llm.py            stub LLM — canned ReAct responses, no API key needed

tests/
  conftest.py           unit test DB fixture (SQLite via tmp_path)
  integration/
    conftest.py         integration test DB fixture (PostgreSQL)
```

## How to use

1. Copy `pyproject.toml`, `alembic.ini`, `alembic/` to the project root
2. Copy `src/` to `src/`
3. Copy `tests/` to `tests/`
4. Replace every occurrence of `appname` / `APPNAME` with the project name
5. Run `uv sync` then `uv run alembic revision --autogenerate -m "init"`
6. Add project-specific models to `src/db/`, routes to `src/api/`, tools to `src/agent/tools.py`
7. Delete `harness/recipes/python/` from the project

## Phase 2 gate

```bash
APPNAME_LLM_PROVIDER=stub uv run pytest          # must be green
uv run python -m src                             # server starts on :8001
curl http://localhost:8001/health                # {"status":"ok","stub_mode":true}
```
