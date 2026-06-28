# Architecture

---

## System Overview

A personal, local-first data-analysis agent for a single power user. The user uploads tabular files and has a back-and-forth conversation to get direct answers with key numbers, interactive charts, and summary tables. It runs entirely on the user's machine as one FastAPI process serving both the JSON API and the static-exported Next.js UI on a single origin (port 8001). The defining architectural constraint is the **privacy boundary**: the LLM (Gemini) only ever sees a dataset's schema/profile and a tiny sample — the agent generates analysis code that executes LOCALLY against the real files, so raw data rows never leave the machine.

## Privacy Boundary

This is the centerpiece of the design and is enforced at the seam between the agent and the LLM.

```
                LOCAL MACHINE (everything below stays here)
  ┌────────────────────────────────────────────────────────────┐
  │  raw files (≤100MB)   profiler        local code executor   │
  │       │                  │                    ▲             │
  │       ▼                  ▼                    │             │
  │   stored on disk ──►  profile + N-row sample  │ runs code   │
  │                          │                    │ over ALL    │
  │                          │                    │ rows        │
  └──────────────────────────┼────────────────────┼────────────┘
                             │ ONLY profile+sample │ ONLY code text
                             ▼                     │
                        ┌─────────────────────────┴──┐
                        │   Gemini (LLM, off-machine) │
                        │  plans + GENERATES code     │
                        └─────────────────────────────┘
```

Rules enforced in code (and asserted by tests):
- The LLM request payload may contain ONLY: the dataset profile, the capped N-row sample, the question, and prior conversation turns. Never the full row set, never raw values beyond the sample.
- The LLM returns a PLAN and CODE TEXT. It never returns computed results — those come from local execution.
- Generated code runs in the local executor against the real file and computes the answer over ALL rows.
- A single chokepoint function builds the LLM context so the boundary is enforced in one place and unit-testable.

## Component Map

```
[Next.js UI  /app/ ]
       │  HTTP (JSON, SSE stream)
       ▼
[FastAPI API  :8001]
       │
       ▼
[Graph runner] ──► [LangGraph agentic_ai graph]
       │                 │ profile → plan → generate_code → execute_local → visualize → finalize
       │                 ├──► [LLM client → Gemini]   (profile + sample only)
       │                 └──► [Local code executor]   (pandas/DuckDB, all rows)
       ▼
[SQLite + filesystem]  (metadata/audit in DB; raw files on disk)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (Next.js static export at `/app/`) | Upload, chat, render code/plan/chart/table, cost display |
| API (FastAPI) | Upload+profile endpoint, ask endpoint (streams steps), library/audit reads |
| Agent (LangGraph) | Plan → generate code → execute locally → summarize → suggest |
| LLM client | Gemini calls; builds the privacy-safe context; reports token usage |
| Local executor | Runs generated pandas/DuckDB code against the real file; captures result, traceback, self-correction |
| Storage | SQLite (profiles, audit) + local filesystem (raw files) |

## Data Flow

1. Trigger: user uploads a CSV via the UI → `POST /datasets`.
2. Profiler loads the file locally, computes the profile + N-row sample, stores file on disk + metadata in DB ([profile_dataset](./capabilities/profile_dataset.md)).
3. User asks a question → `POST /datasets/{id}/ask` → graph runs: plan → generate_code (Gemini, profile+sample only) → execute_local (code over all rows) → visualize (chart type + follow-ups).
4. Step status streams live to the UI (SSE); each step is persisted.
5. Output: a direct answer + key numbers + the exact code (collapsible) + an interactive chart + summary table + token/cost, persisted as an immutable [Turn](./data.md#entity-turn).

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API | planning + code generation + chart/follow-up choice | retry once, then surface a flagged best-guess or a readable error; no offline stub |
| Local filesystem | raw file storage + execution input | request-scoped fatal with clear message |

## Stack

- **Language:** Python 3.12
- **Agent framework:** LangGraph (multi-step plan→generate→execute→visualize pipeline with conditional error edges)
- **LLM provider + model:** Gemini — default `gemini-2.5-flash` (fast; many calls/day). Configured via `AGENT_GEMINI_API_KEY` already in `.env`; provider exists at `src/llm/providers/gemini.py`.
  > **Assumed:** model defaulted to `gemini-2.5-flash` (the skeleton's provider defaults to `gemini-2.5-pro`); set `AGENT_LLM_MODEL=gemini-2.5-flash` for latency. Override in `.env`.
- **Backend:** FastAPI (boilerplate skeleton)
- **Database + ORM:** SQLite + SQLAlchemy 2.0 + Alembic (`AGENT_DATABASE_URL`). Local-first single-user — SQLite is the intended fit.
- **Frontend:** Next.js 15 + React 19, static export served at `/app/` on the single FastAPI origin.
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | existing | agent graph |
| google-genai | existing | Gemini client |
| pandas | latest | local profiling + analysis execution |
| duckdb | latest | local SQL-style execution over files for larger/aggregation queries |
| openpyxl | latest | Excel read (later phase) |
| Recharts | latest | interactive client-side charts |

**Avoid:** sending raw rows to the LLM (privacy boundary); executing LLM-returned code with unrestricted `os`/network access — the executor restricts builtins and runs code with the dataframe pre-loaded, no filesystem-write or network by the generated code; SQLite-as-substitute concerns do not apply (SQLite is the real DB here).

## Deployment Model

A single long-running local process: `uv run python -m src` on port 8001 serves the API and the built UI at `/app/`. No cloud, no multi-tenant. Single user, many invocations per day.
