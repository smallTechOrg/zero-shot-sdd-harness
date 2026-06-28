# Architecture

## System Overview

A single FastAPI process serves both the JSON/SSE API and the static-export Next.js UI (single origin, `http://localhost:8001/app/`). The user uploads tabular files which are stored locally and auto-profiled. Conversational queries run through a LangGraph agent that **plans → generates pandas → executes locally → summarizes**. Gemini is the LLM; it receives only schema and summaries. Generated pandas runs in a restricted local subprocess against the real data. All runs persist to SQLite as an audit trail.

## Component Map

```
Browser (Next.js static export @ /app/)
   │  upload file / ask question (SSE stream)
   ▼
FastAPI (src/api)  ──────────────────────────────┐
   │ ingest+profile (src/data)                    │ structured logs (structlog)
   ▼                                              │ + optional LangSmith trace
LangGraph agent (src/graph + src/analysis)        │
   │ plan ─► generate_code ─► execute_locally ─► summarize
   │   ▲ schema/summary only          │ pandas
   │   └──────── Gemini (src/llm) ─────┘ (NEVER raw rows)
   ▼                                   ▼
SQLite (src/db): datasets, profiles,   Local sandbox subprocess (src/execution)
sessions, queries (audit trail)        reads real rows from local file storage
```

## Layers

| Layer | Path | Responsibility |
|-------|------|----------------|
| API | `src/api/` | Upload, profile, query (SSE), sessions, cost, audit endpoints; mounts static UI at `/app`. |
| Ingest + profile | `src/data/` | Save uploaded file locally; load CSV/Excel; compute column profiles & summaries (no row export). |
| Execution sandbox | `src/execution/` | Run LLM-generated pandas in a restricted subprocess against the local data file; capture result. |
| Analysis | `src/analysis/` | Planner, code-generation prompt assembly, result→viz/summary helpers. |
| Agent graph | `src/graph/` | LangGraph state, nodes, edges, streaming runner. |
| LLM client | `src/llm/` | Provider abstraction; Gemini provider (existing). Streaming + token usage. |
| Persistence | `src/db/` | SQLAlchemy models, session, migrations; SQLite audit trail + library. |
| Observability | `src/observability/` | structlog config + run/step events; optional LangSmith. |
| Frontend | `frontend/` | Next.js static export: upload, profile, chat, streamed answer, shown code; charts/tables in later phases. |

## Data Flow (one query)

1. Trigger: UI POSTs the question + `session_id` + `dataset_id` to `POST /sessions/{id}/query` (SSE).
2. Runner loads the dataset **profile/summary** (not rows) and conversation history.
3. `plan` node: Gemini gets schema + profile + history → returns an analysis plan. **(schema/summary only)**
4. `generate_code` node: Gemini gets plan + schema → returns pandas code referencing a `df` variable. **(no rows)**
5. `execute_locally` node: sandbox subprocess loads the real file into `df`, runs the code, captures a structured result. **(rows stay local)**
6. `summarize` node: Gemini gets the *result summary/aggregates* (not rows) → returns the plain-language answer, streamed.
7. Output: `finalize` persists query, generated code, result, token usage; streams a completion event.

See [agent.md](agent.md) for the explicit per-node privacy boundary.

## Privacy Boundary

The single most important architectural invariant. See also [agent.md](agent.md#privacy--context).

| Data | Goes to LLM? | Stays local? |
|------|--------------|--------------|
| Column names, dtypes | yes | — |
| Column profiles (min/max/mean/missing count/distinct count, top categories) | yes | — |
| Aggregates & result summaries (the *output* of executed code, when not row-level) | yes | — |
| Generated pandas code | yes (LLM authored it) | — |
| **Raw data rows / cell values / individual records** | **NEVER** | **always local** |
| Uploaded file bytes | never | local file storage |

Enforcement: the `execute_locally` node is the only code with access to row data; it runs out-of-process. Nodes that call the LLM receive only typed profile/summary objects, never a DataFrame. A test asserts no LLM-bound payload contains raw rows.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (`google-genai`) | plan / codegen / summarize | retry w/ backoff; on persistent failure set `state.error` → handle_error → surfaced to UI |
| Local sandbox subprocess | execute pandas | timeout/crash captured as execution error; agent reports failed analysis, no app crash |
| SQLite | library + audit trail | fatal at startup if unwritable; surfaced as 500 |

## Stack

- **Language:** Python 3.11+ (backend), TypeScript/React (frontend). Matches existing skeleton.
- **Agent framework:** LangGraph (existing wiring kept and extended).
- **LLM provider + model:** Google Gemini via `google-genai`. Key in `.env` as `AGENT_GEMINI_API_KEY`. Default model `gemini-2.0-flash` (env-configurable via `AGENT_LLM_MODEL`).
  > **Assumed:** `gemini-2.0-flash` is the default model; one model for all nodes in v1.
- **Backend:** FastAPI + uvicorn, single process, serves SSE for streaming. Port 8001.
- **Database + ORM:** SQLite via SQLAlchemy 2.0 + Alembic. `AGENT_DATABASE_URL` default `sqlite:///./data/agent.db`.
  > **Assumed:** SQLite is the production DB (not a Postgres substitute) because this is a single-user, single-machine personal tool with no concurrency needs. SQLite is therefore the gate DB.
- **Frontend:** Next.js 15 static export (`output: 'export'`) → `frontend/out/`, mounted at `/app`. Charts via Vega-Lite (`vega-embed`) in Phase 2.
- **Code-execution sandbox:** local subprocess (`subprocess` + resource limits) running pandas; no network, no fs writes outside a temp dir, wall-clock + memory caps.
  > **Assumed:** subprocess-with-resource-limits is sufficient sandboxing for a single-user local tool (no containerization for v1).
- **Dependency management:** uv (Python), pnpm (TypeScript).

| Key library | Version | Purpose |
|-------------|---------|---------|
| pandas | >=2.2 | data load + analysis (in sandbox) |
| openpyxl | >=3.1 | Excel ingestion (Phase 3) |
| google-genai | >=2.9 | Gemini provider (existing) |
| langgraph | >=0.1 | agent graph (existing) |
| structlog | >=24.1 | structured observability (existing) |
| vega-embed | latest | chart rendering (frontend, Phase 2) |

**Avoid:** any path that sends a DataFrame / raw rows to the LLM; SQLite-as-substitute reasoning (here SQLite is the real prod DB); cloud execution of generated code.

## Observability

| Signal | What | Where |
|--------|------|-------|
| Trace | one trace per query, one span per node | structlog (Phase 1); optional LangSmith via `LANGCHAIN_TRACING_V2`/`LANGCHAIN_API_KEY` |
| LLM calls | prompt/completion tokens, latency, model, **payload privacy assertion** | structured log |
| Execution | code run, duration, success/error | structured log + `queries` table |
| Run outcome | status, total duration, error | DB + structured log |

## Deployment Model

Single long-running local process: `uv run python -m src` (uvicorn on `:8001`), serving the prebuilt `frontend/out/` at `/app/`. Build the UI first with `cd frontend && pnpm build`.

> **Assumed:** Backend imports use bare module names with `pythonpath=["src"]` (existing skeleton convention), e.g. `from graph.state import AgentState`, not `from src.graph...`.
