# Architecture

> System design for the Local Data Analyst. Two ideas are central and architecture-defining: (1) the **privacy boundary** — raw rows never reach the LLM, only schema + aggregates; and (2) the **local-execution model** — the LLM plans and phrases, but all analysis runs locally in DuckDB.

---

## System Overview

A single local user drives a Next.js web UI (served by FastAPI at one origin, `http://localhost:8001/app/`). They upload a CSV, which FastAPI ingests into a **local DuckDB** file and profiles. When they ask a question, a **LangGraph** pipeline plans a strategy, generates **DuckDB SQL**, runs it **locally**, and phrases a plain-English answer. The LLM (Gemini) is consulted only twice on the happy path — once to plan + write SQL (seeing only the column schema), and once to phrase the answer (seeing only the small aggregate result). DuckDB does the data work; the LLM never sees a raw row. App state (datasets, question runs, plans, SQL, traces, cost) persists in **SQLite** via SQLAlchemy.

## Privacy Boundary (architecture-defining)

The hard rule: **raw data rows never leave the machine.** Concretely:

- DuckDB holds and queries the full dataset locally. The full result table is returned to the **browser** (local), not to the LLM.
- The LLM receives only: (a) the **column schema** (names + DuckDB types + a tiny health summary like null-counts and a couple of example *value shapes*, never full rows), and (b) **aggregate / summary results** — small, bounded result sets (the agent caps rows sent to the LLM, e.g. ≤ 50 aggregated rows) used to phrase the answer.
- A named graph node — **`privacy_guard`** — runs before every LLM call that carries result data and asserts the payload contains only schema + bounded aggregates (row-count cap, no full-table dumps). If a payload would exceed the cap or carry raw detail rows, the guard truncates to a summary / aggregate and records that it did so in the trace. The guard is the single chokepoint; no node calls the LLM with result data without passing through it.
- Every LLM input is logged (structured) so the privacy property is **auditable** — a test asserts no raw row value appears in any logged LLM input.

## Local-Execution Model (architecture-defining)

The LLM is a **planner and phraser**, not a data processor. The loop is: LLM proposes DuckDB SQL → the **system** executes it locally against DuckDB → the system aggregates → only the aggregate goes back to the LLM to phrase. This keeps data local, keeps cost low (small payloads), and makes the answer auditable (the exact SQL is shown). It also bounds latency: DuckDB scans ~100MB columnar data in well under the ~30s budget.

## Component Map

```
                          Browser (Next.js static export @ /app/)
                          upload • profile card • ask • answer • chart • table • show-its-work
                                            │  HTTP (single origin :8001)
                                            ▼
                          FastAPI app (src/api)  — ok()/api_error() envelope
                          POST /datasets • GET /datasets/{id} • POST /datasets/{id}/ask
                                            │
                ┌───────────────────────────┼───────────────────────────┐
                ▼                            ▼                           ▼
       Analysis engine (src/analysis)   LangGraph pipeline        SQLAlchemy / SQLite
       DuckDB ingest • schema •         (src/graph)               (src/db) datasets,
       profile • LOCAL SQL exec         plan→guard→sql→run→       question_runs (plan,
       (dialect-safe, retry)            retry→phrase→chart        sql, trace, cost)
                │                            │
                ▼                            ▼
        Local DuckDB file              Gemini (LLM)  ◄── only schema + aggregates ever
        (full data, never              gemini-3.1-pro-preview  (enforced by privacy_guard)
         leaves machine)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| **Web UI** (`frontend/`) | Upload, render profile, ask, render answer + ONE chart + summary table, collapsible show-its-work, labelled stubs. Static export served by FastAPI. |
| **API** (`src/api`) | HTTP endpoints, request validation, `ok(data)` / `api_error(code,msg,status)` envelope, calls the runner. |
| **Agent** (`src/graph`) | LangGraph StateGraph: plan → privacy_guard → generate_sql → execute_sql → (retry on error) → phrase_answer → pick_chart → finalize / handle_error. |
| **Analysis engine** (`src/analysis`) | DuckDB ingest (CSV → local DB), schema extraction, profiling, **dialect-safe local SQL execution**, chart-type heuristic. No LLM calls. |
| **LLM** (`src/llm`) | `LLMClient` + `GeminiProvider` (default `gemini-3.1-pro-preview`). Returns text + token-usage for cost. |
| **Storage** (`src/db`) | SQLAlchemy models + session; SQLite for app state. DuckDB files live under `data/duckdb/`. |
| **Observability** (`src/observability`) | Structured logging of each LLM call (model, prompt, output, tokens, latency) and each run outcome to stdout + the DB. |

## Data Flow

**Upload + profile** (`POST /datasets`):
1. Trigger: user uploads a CSV in the browser.
2. API saves the file under `data/uploads/{dataset_id}/` and calls the analysis engine.
3. Engine ingests the CSV into a local DuckDB table, extracts the **schema** (column names, inferred DuckDB types) and computes a **profile** (row count, per-column null counts, distinct counts, min/max for numerics) — all locally, no LLM.
4. A `datasets` row is written (name, path, schema JSON, profile JSON, status).
5. Output: the profile card (rows, columns, types, health summary). **No LLM call on upload.**

**Ask** (`POST /datasets/{id}/ask`):
1. Trigger: user asks a natural-language question on the loaded dataset.
2. `plan` node — LLM call #1: given the question + **schema only**, produce a short plan + the proposed DuckDB SQL (structured JSON). The prompt declares "you are writing DuckDB SQL" and forbids SQLite-isms.
3. `privacy_guard` node — asserts the plan prompt carried only schema (no rows). (Guard also gates the later phrasing call.)
4. `execute_sql` node — runs the SQL **locally** in DuckDB. On a SQL error (e.g. unknown function), set `sql_error` and route to retry.
5. `retry` edge — feed the error + the failed SQL back to the LLM (LLM call, schema + error only) to regenerate corrected SQL, up to `MAX_SQL_RETRIES` (3). The trace records each attempt (SQL, error or success).
6. `phrase_answer` node — privacy_guard bounds the result to a small aggregate, then LLM call #2 phrases a plain-English answer with key numbers, seeing **only the aggregate**.
7. `pick_chart` node — a deterministic heuristic over the aggregate result shape picks ONE chart type (bar / line / pie / table-only) — no LLM.
8. `finalize` — persist `question_runs` row (plan, SQL, trace, result, chart spec, cost, status); return the answer + chart data + summary table + trace to the browser.
9. Output: answer + key numbers + ONE chart + summary table + collapsible show-its-work. The **full result table renders locally** in the browser.

See [`agent.md`](agent.md) for the full node/edge specification.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (`gemini-3.1-pro-preview`) | Plan + SQL generation, answer phrasing. | Plan/phrase failure → `handle_error` sets run failed, surfaces a clear message; SQL-gen failure inside the retry loop regenerates; on exhausting retries, the run fails with the last SQL error shown. |
| DuckDB (in-process, local) | Ingest + all analysis. | Ingest error → dataset status `failed` with reason; SQL execution error → retry loop (feed error back to LLM). |
| SQLite (in-process, local) | App state persistence. | Standard DB error → 500 via `api_error`. |

## Stack

> Concrete choices for THIS project. Generic rules (model-naming, DB driver, dev port, real-key tests) live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.11+ (matches skeleton `requires-python = ">=3.11"`); TypeScript for the frontend.
- **Agent framework:** LangGraph (`StateGraph`) — extends the skeleton's graph.
- **LLM provider + model:** Gemini, `gemini-3.1-pro-preview` (the skeleton's `GeminiProvider.DEFAULT_MODEL` — this is the ID the live Gemini API serves for the gemini-3.1-pro family; the bare `gemini-3.1-pro` returns 404). Key `AGENT_GEMINI_API_KEY`, env prefix `AGENT_`. Provider auto-detected by `LLMClient`.
- **Backend:** FastAPI (skeleton app factory + single-origin `/app/` static serve).
- **Database + ORM:** SQLite (`AGENT_DATABASE_URL=sqlite:///./data/agent.db`) for app state via SQLAlchemy 2.0; **DuckDB** (local file per analysis) for data — DuckDB is NOT behind SQLAlchemy, it is the analytics engine accessed directly by `src/analysis`.
- **Frontend:** Next.js 15 + React 19, static export, Tailwind v4 (skeleton). Charts via a lightweight client lib (see key libraries).
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| duckdb | >=1.1 | Local columnar analysis engine. **Add to `pyproject.toml` (Phase-1 `analysis-engine` slice).** |
| langgraph | >=0.1 | Agent graph (skeleton). |
| google-genai | >=2.9 | Gemini client (skeleton). |
| sqlalchemy | >=2.0 | App-state ORM (skeleton). |
| alembic | >=1.13 | Migrations (skeleton). |
| recharts | ^2 | Client-side chart rendering (bar/line/pie) in the browser. **Add to `frontend/package.json` (Phase-1 `frontend-ui` slice).** |
| @playwright/test | ^1 | E2E smoke tests. **Add to `frontend/package.json` (Phase-1 `e2e-tests` slice).** |

**Avoid:** Pandas/Polars for the analysis path (DuckDB is the engine — no second dataframe layer). Any path that sends raw rows to the LLM. SQLite functions in generated SQL (DuckDB dialect only). A hardcoded op-list interpreter for questions (always generate executable DuckDB SQL — see `agentic-ai.md` #22).

## Deployment Model

A long-running local process: `uv run python -m src` starts uvicorn on `:8001`; the frontend is pre-built (`cd frontend && pnpm build`) into `frontend/out/` and mounted at `/app/`. Single user, single machine. SQLite at `data/agent.db`; DuckDB files under `data/duckdb/`; uploads under `data/uploads/`. Observability is stdout structured logs + the DB. No cloud, no auth, no external network beyond the Gemini API.
