# Architecture

## System Overview

A single-machine personal data-analysis agent. A Next.js chat UI (static-export, served by
the backend at `/app`) talks to a FastAPI backend. The backend stores uploaded files on the
local filesystem, profiles them, and runs an agentic LangGraph loop that asks Gemini to write
pandas analysis code, executes that code LOCALLY against the user's data, verifies the result,
and iterates until it holds or a step cap is reached. Schema, bounded samples, and aggregates
are the ONLY data-derived content ever placed in an LLM prompt — raw rows never leave the
machine. Every query and its exact code/result are persisted to SQLite for a reproducible audit.

## Components

| Component | Responsibility |
|-----------|----------------|
| Next.js chat UI (`frontend/`) | Upload, profile display, chat transcript, answer + chart + collapsible code, labelled stubs. Static export served at `/app`. |
| FastAPI app (`src/api/`) | HTTP surface: upload + profile (`datasets`), analyze + run-history (`analyses`), health. |
| Dataset store | Uploaded files written under a local data dir; metadata + profile in DB. |
| Profiler (`src/analysis/profile.py`) | On upload, computes columns, dtypes, value ranges, missing counts, and a bounded row sample. |
| LangGraph agent (`src/graph/`) | The plan→codegen→execute→verify→iterate loop; see [agent.md](agent.md). |
| Local executor (`src/analysis/executor.py`) | Runs LLM-generated pandas code against the full DataFrame in a constrained namespace; returns result + chart spec. |
| LLM client (`src/llm/`) | Provider-pluggable; Gemini by default. Receives only schema/sample/aggregates. |
| Persistence (`src/db/`, SQLAlchemy + Alembic) | `datasets` and `analyses` tables; run-history audit. See [data.md](data.md). |
| Observability (`src/observability/`) | Structured per-step request/response/latency logging to stdout; LangSmith tracing when enabled. |

## Layers

1. **Presentation** — Next.js UI.
2. **API** — FastAPI routers (`src/api/`).
3. **Orchestration** — LangGraph agent + runner (`src/graph/`).
4. **Execution / domain** — profiler + local code executor (`src/analysis/`).
5. **Persistence** — SQLAlchemy models + Alembic migrations (`src/db/`).
6. **Integration** — LLM client (`src/llm/`), observability.

## Data Flow (Phase 1)

1. **Upload** — UI POSTs a CSV → `datasets` endpoint saves the file locally, the profiler
   computes the profile + bounded sample, a `datasets` row is written, the profile is returned.
2. **Ask** — UI POSTs `{dataset_id, question}` → `analyses` endpoint creates an `analyses` row
   (status `running`) and invokes the agent.
3. **Agentic loop** — plan node builds a prompt from **schema + sample + aggregates only**;
   codegen node asks Gemini for pandas code; executor runs that code LOCALLY against the full
   DataFrame; verify node checks the result is well-formed (and re-plans on error/empty);
   iterate up to the step cap. See [agent.md](agent.md).
4. **Answer** — final node assembles prose + chart spec (Vega-Lite JSON) + the exact code;
   the `analyses` row is updated to `completed` with question, code, result, chart spec,
   timestamp.
5. **Audit** — UI renders the answer; the run is retrievable via run-history.

## Privacy Boundary (hard, central)

- The ONLY data-derived content allowed in an LLM prompt is: column schema, a bounded row
  sample (configurable cap, default small), and aggregates (counts, min/max/mean, missing
  counts, distinct counts). This is constructed in one place (the prompt builder) and covered
  by a test asserting no full-data payload is sent.
- The LLM emits **code**, not answers-from-data. All computation over real rows happens locally
  in the executor.
- Analysis always runs over the **full** DataFrame, not the sample — the sample exists only to
  inform code generation.

## Local Execution Sandbox Approach

- LLM-generated code runs in a constrained namespace exposing only `df` (and named frames in
  later phases), `pd`, and a small whitelisted helper set; builtins are restricted (no
  `open`, `__import__`, `eval`, `exec`, network, filesystem writes).
- Execution is time-bounded and the result is validated/coerced to a serializable shape.
- Any execution error is captured and fed back to the loop for regeneration (not crashed).

> **Assumed:** Phase 1 uses a restricted-namespace in-process executor (not a container/VM
> sandbox), acceptable because the only code run is LLM-generated for a single trusted local
> user; container isolation is deferred unless a later phase requires it.

## External Dependencies

- **Google Gemini API** (`gemini-2.5-flash`) — planning / code generation. Key via `.env`.
- **LangSmith** (optional) — tracing when `LANGCHAIN_TRACING_V2=true`.
- Local filesystem — uploaded files and SQLite DB file.

## Deployment Model

Single-machine, single-user. `cd frontend && pnpm build` produces the static export;
`uv run python -m src` serves the API and the UI at `http://localhost:8001/app/`. SQLite file
and uploads live in a local data directory. No multi-user auth, no cloud data egress.

## Stack

| Concern | Choice |
|---------|--------|
| Language | Python 3.12 (backend), TypeScript/React 19 (frontend) |
| Agent framework | LangGraph |
| LLM provider + model | Google Gemini, `gemini-2.5-flash` (env-configurable via `*_LLM_MODEL`) |
| Backend | FastAPI |
| Database + ORM | SQLite via SQLAlchemy + Alembic |
| Data engine | pandas (local execution + profiling) |
| Frontend | Next.js 15 static export (`output: 'export'`, `basePath: '/app'`), React 19 |
| Charts | Vega-Lite JSON spec rendered client-side |
| Dependency mgmt | uv (Python), pnpm (frontend) |
| E2E testing | Playwright (`frontend/tests/e2e/`) |
| Observability | structured stdout logging always; LangSmith tracing when enabled |
| Dev port | 8001 |

> **Assumed:** charts are emitted as a Vega-Lite JSON spec (chart type + encodings chosen by
> the agent) and rendered client-side; the backend never renders images.
