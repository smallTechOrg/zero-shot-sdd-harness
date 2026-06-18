# DataChat v0.1 — Implementation Plan

**Agent slug:** `data-analyst`  
**Branch:** `feature/data-analyst-v0.1`  
**Created:** 2026-06-18

---

## Phase 1 — Domain Models + DB Schema

**Goal:** SQLite tables for Session and Message entities are created, all CRUD works, and unit tests pass.

### Tasks

1. Create `pyproject.toml` with all Python dependencies
2. Implement `src/data_analyst/config/settings.py` — Pydantic BaseSettings with `DATA_ANALYST_` prefix
3. Implement `src/data_analyst/domain/models.py` — Pydantic domain models (Session, Message)
4. Implement `src/data_analyst/db/models.py` — SQLAlchemy 2.0 Mapped types (SessionRow, MessageRow)
5. Implement `src/data_analyst/db/session.py` — engine + sessionmaker + init_db
6. Create `alembic/script.py.mako` — verbatim mako template (required before any alembic command)
7. Create `alembic/env.py` and `alembic.ini`
8. Run `uv run alembic revision --autogenerate -m "initial"` → generates `alembic/versions/0001_initial.py`
9. Run `uv run alembic upgrade head` and verify with `uv run alembic current`
10. Implement `tests/conftest.py` and `tests/unit/` — unit tests for domain models and DB models
11. Commit: `phase-1: domain models + schema — gate PASSED`

**Gate:** `uv run pytest tests/unit/ -v` — 100% pass

---

## Phase 2 — Stubbed Agent Loop + FastAPI API + React Frontend + README

**Goal:** Full pipeline runs end-to-end with stubs. File upload works. Chat Q&A returns stub answer. Integration test passes. Golden-path UI smoke test green.

### Tasks

1. Implement `src/data_analyst/tools/pandas_executor.py` — sandboxed pandas executor (stub: returns static result)
2. Implement `src/data_analyst/graph/state.py` — `AgentState` TypedDict with all ReAct fields
3. Implement `src/data_analyst/graph/nodes.py` — all 6 nodes (setup, plan_action, execute_action, finalize, force_finalize, handle_error) — stubs in Phase 2
4. Implement `src/data_analyst/graph/edges.py` — routing functions (iteration guard + FINAL ANSWER check)
5. Implement `src/data_analyst/graph/agent.py` — LangGraph `StateGraph` compiled at startup
6. Implement `src/data_analyst/graph/runner.py` — `run_agent(session_id, question)` entry point
7. Implement `src/data_analyst/llm/providers/` — base, stub, gemini providers + factory (provider=auto)
8. Implement FastAPI app: `src/data_analyst/api/__init__.py` (create_app + lifespan), `api/_common.py`, `api/sessions.py`, `api/chat.py`
9. Implement `src/data_analyst/__main__.py` — `uvicorn` on port 8001
10. Scaffold React frontend: `src/frontend/` — Vite + TypeScript, Upload screen + Chat screen with stub-mode banner
11. Write `tests/integration/test_pipeline.py` — stub run, one session record, status=completed
12. Write `tests/integration/test_golden_path.py` — golden-path HTTP smoke test via TestClient
13. Write `README.md` — setup, how to run, test commands (all prefixed `uv run`)
14. Live-server check: start app, hit `/health` and upload endpoint via curl
15. Commit: `phase-2: stubbed agent loop + API + frontend + README — gate PASSED`

**Gate:** `uv run pytest tests/ -v` — 100% pass (no LLM API key required)

---

## Deferred to Future Phases

- Phase 3: Real Gemini LLM integration (replace stubs with live calls)
- Phase 4: Visual dashboards and chart generation
- Phase 5: Automated insights and data profiling
- Phase 6: Multi-user auth and data isolation
- Phase 7: Export/download results
- Phase 8: Multi-file uploads per session
