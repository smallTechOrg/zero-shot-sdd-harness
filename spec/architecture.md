# Architecture

How the personal data-analysis agent is put together. This extends the existing `src/` skeleton (FastAPI + LangGraph + SQLite + Gemini) **in place** — no second package, no rename of the working plumbing.

---

## System Overview

A single local user drives a Next.js static-export web UI (served single-origin by FastAPI at `http://localhost:8001/app/`). The UI uploads a spreadsheet, which the backend profiles and stores locally, then submits plain-language questions. Each question runs through a LangGraph agent: the LLM writes pandas code from **only the schema + sample rows + question**, the backend runs that code **locally against the full dataset in a subprocess**, retries on error, and a second LLM call turns the computed result into a plain-language answer, narrative, key numbers, a Vega-Lite chart, and a summary table. The raw data never leaves the machine; the exact code is always returned for audit.

## Component Map

```
Browser (Next.js static export @ /app/)
    │  multipart upload / JSON question
    ▼
FastAPI (src/api)  ──────────────►  SQLite (datasets, runs) via SQLAlchemy 2.0
    │                                        ▲
    │ run_analysis(dataset_id, question)     │ persist run + result
    ▼                                        │
LangGraph agent (src/graph)  ───────────────┘
    │  load_context → generate_code → execute_code ⇄ (retry) → write_answer
    │                        │              │                      │
    │            schema+sample+question     │            aggregated result only
    ▼                        ▼              ▼                      ▼
src/analysis            Gemini (google-genai)   Local pandas       Gemini
(loader/profiler/       via LLMClient           subprocess         via LLMClient
 executor/charts)       [schema leaves]         [raw data local]   [aggregate leaves]
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| **UI** (`frontend/`) | Upload box, profile card, chat, answer render (chart via `vega-embed`, table, collapsible code), labelled stubs. |
| **API** (`src/api`) | FastAPI routers: `datasets` (upload/profile/list/get), `runs` (ask/get). Uniform `ok()` / `api_error()` envelope. Serves the static UI at `/app`. |
| **Agent** (`src/graph`) | LangGraph `StateGraph` — the ask→code→execute→retry→answer loop; the runner persists the run. |
| **Analysis** (`src/analysis`) | Pure functions: read CSV/Excel, profile a DataFrame, execute generated pandas in a timed subprocess, build a Vega-Lite spec. No LLM, no DB. |
| **LLM** (`src/llm`) | Existing `LLMClient` wrapper + Gemini provider. Untouched interface; the graph nodes call `LLMClient().call_model(...)`. |
| **Storage** (`src/db`) | SQLAlchemy models + session. `datasets` and `runs` tables. Uploaded files stored on the local filesystem under `data/datasets/`. |

## Data Flow

1. **Trigger — upload:** user POSTs a CSV/Excel to `POST /datasets`. `loader` reads it (size-guarded), stores the file under `data/datasets/<id>.<ext>`, `profiler` computes columns/types/row-count/quality-flags + sample rows, a `datasets` row is written, and the profile card is returned.
2. **Trigger — question:** user POSTs `{dataset_id, question}` to `POST /runs`. A `runs` row is created (`status=running`) and `run_analysis` invokes the graph.
3. **load_context:** loads the dataset's schema, sample rows, row count from the `datasets` row (no LLM, no file read of full data).
4. **generate_code:** LLM (Gemini) receives schema + sample rows + question (+ prior error on retry) and returns pandas code that assigns a compact aggregated `result`.
5. **execute_code:** `executor` runs that code in a **subprocess** with a timeout, reading the full dataset from its local file. Returns the aggregated `result` or an error string.
6. **retry loop:** on execution error and `attempts < AGENT_MAX_CODE_RETRIES`, route back to `generate_code` with the error; otherwise on repeated failure route to `handle_error`.
7. **write_answer:** LLM receives the question + the aggregated `result` (small, not raw rows) and returns JSON: plain answer, narrative, key numbers, and a typed chart selection. `charts` validates it and builds a Vega-Lite spec.
8. **finalize / Output:** the `runs` row is updated with code, result, answer, narrative, key numbers, chart spec, table, status. The API returns the full run; the UI renders answer + chart + table + collapsible code.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini (`google-genai`) | `generate_code` and `write_answer` LLM calls | Node catches the exception, sets `state["error"]`, routes to `handle_error`; run persisted as `failed` with the message surfaced in the API response. |
| Local filesystem (`data/datasets/`) | Stored uploaded files + SQLite DB file | Upload/load errors return `api_error`; missing file at analysis time → `load_context` sets `error`. |
| pandas subprocess | Local execution of generated code | Non-zero exit / timeout / traceback captured as an execution error string → drives the retry loop, never crashes the server. |

## Stack

> This project's concrete choices. Generic every-project rules (model-naming, DB driver, dev port, real-key tests) live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.11+ (backend), TypeScript (frontend).
- **Agent framework:** LangGraph (`StateGraph`, already wired) — the `transform_text` slot is replaced by the analysis graph.
- **LLM provider + model:** Google Gemini via `google-genai`; Phase 1 uses the repo default `gemini-3.1-pro` (leave `AGENT_LLM_MODEL` blank). Provider auto-detected from `AGENT_GEMINI_API_KEY`. Phase 2 may set a cheaper Gemini model via `AGENT_LLM_MODEL` for cost-awareness.
- **Backend:** FastAPI (single-origin: serves the static UI at `/app` and the JSON API).
- **Database + ORM:** SQLite (production DB here IS SQLite) at `AGENT_DATABASE_URL=sqlite:///./data/agent.db`, SQLAlchemy 2.0 declarative + Alembic migrations.
- **Frontend:** Next.js 15 static export (`output: 'export'`, `basePath: '/app'`) + React 19 + Tailwind v4, served by FastAPI.
- **Dependency management:** uv + `pyproject.toml` (backend); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| pandas | >=2.2 | Local data loading + generated-code execution |
| openpyxl | >=3.1 | Excel (`.xlsx`) read support for pandas |
| langgraph | >=0.1 | Agent graph (already present) |
| google-genai | >=2.9 | Gemini client (already present) |
| sqlalchemy / alembic | >=2.0 / >=1.13 | ORM + migrations (already present) |
| structlog | >=24.1 | Structured request/response + node logging (already present) |
| vega / vega-lite / vega-embed | ^6 / ^5 / ^6 | Frontend chart rendering from server-emitted Vega-Lite specs |

**Avoid:**
- No new agent package beside `src/` — extend the existing graph in place.
- No repository pattern / service layer — call SQLAlchemy sessions directly as the skeleton does.
- No sending raw data rows to the LLM — only schema, sample rows, aggregated results, and the question.
- No in-process `exec` of generated code without a timeout — always the timed subprocess (`src/analysis/executor.py`).
- No charting library that needs raw rows on the server side — emit Vega-Lite specs with the small aggregated data embedded.

## Deployment Model

A long-running local single-origin service: `uv run python -m src` starts uvicorn on port 8001, serving both the JSON API and the built `frontend/out/`. SQLite and uploaded files live under `data/`. One user, one machine, no auth.
