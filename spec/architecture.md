# Architecture

---

## System Overview

A single-user, locally-run web app. A FastAPI process (`api:app`, port `:8001`) serves both the JSON API and the built Next.js static export at `/app/`. The user uploads a CSV; the file is stored locally and profiled. When the user asks a question, FastAPI starts a LangGraph run that **plans → writes pandas code → executes that code in a local subprocess sandbox over the full file → observes the result → retries on error → finalizes**. Only schema + a small sample + the question ever reach the Gemini LLM; the raw data stays local. The agent streams its plan/steps/retries to the browser over SSE and persists the full run (plan, every code attempt + result, answer, chart spec, table) to SQLite as an audit trail.

## Component Map

```
[Browser :8001/app/ — Next.js export]
        │  upload CSV / ask question / SSE step stream
        ▼
[FastAPI api:app]
   ├─ api/datasets.py  → store file + profile      ──► [local filesystem: src/data/datasets/<id>/]
   ├─ api/analysis.py  → create run, SSE stream, fetch run
        │
        ▼
[graph/runner.py::run_agent]  ──►  [LangGraph agentic_ai]
   plan ─► generate_code ─► execute_code ─► observe ─►(retry|finalize)
                                │ local execution only
                                ▼
                    [analyst/sandbox.py — subprocess]
                       loads FULL csv via pandas, runs generated code,
                       captures result/chart-spec/table/stdout, timeout
   │ LLM calls (plan, code-gen, regen) — schema + sample + question ONLY
   ▼
[llm/client.py → Gemini gemini-3.1-pro]

[db/session.py → SQLite (SQLAlchemy 2.0 + Alembic)]  ◄── datasets, runs
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (`frontend/`) | Upload control, question box, live SSE step stream, answer + chart + table + collapsible code; labelled stubs for later features. |
| API (`src/api/`) | `datasets` (upload + profile), `analysis` (create run, SSE stream, fetch run). Envelope `ok()` / `api_error()`. |
| Agent (`src/graph/`) | LangGraph plan→code→execute→observe→retry→finalize loop; the only place the LLM is called (plan/code/regen). |
| Sandbox (`src/analyst/`) | Local subprocess that loads the full CSV and runs generated pandas; builds chart spec + table; enforces timeout. **No data ever leaves here toward the LLM.** |
| Storage (`src/db/`, filesystem) | SQLite for `datasets`/`runs` audit trail; CSV files on local disk under `src/data/datasets/<id>/`. |

## Data Flow

1. **Trigger:** user uploads a CSV via `POST /datasets` → file saved to `src/data/datasets/<uuid>/<filename>`, lightweight schema (columns + dtypes + ≤ 20 sample rows) computed and stored; `datasets` row created.
2. User asks a question via `POST /datasets/{id}/runs` → a `runs` row is created (`status=running`), `run_agent` is dispatched, and the response returns the `run_id` immediately.
3. The browser opens `GET /runs/{id}/stream` (SSE). The graph runs: **plan** (LLM, cheap) → **generate_code** (LLM: schema+sample+question → pandas) → **execute_code** (local subprocess over the FULL file) → **observe**. On error, the error text is fed back and `generate_code` runs again, up to the retry cap. Each transition emits an SSE event (plan / step / retry-with-error / final).
4. **Output:** on success, `finalize` writes the plain-English `answer`, `chart_spec` (Plotly JSON), and `table` (JSON) to the run, status `completed`. The browser renders answer + interactive chart + summary table + collapsible code. The full audit trail (plan + every attempt) is persisted.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (`gemini-3.1-pro`) | Plan + pandas code generation + regen on retry | Run ends `failed` with a clear error surfaced to the UI; no fallback (single-user, retry by re-asking). |
| Local pandas subprocess | Execute generated code over the full file | Captured exception → fed back as a retry; after retry cap, run ends `failed` with the last error shown. |
| SQLite (local file) | Persist datasets + runs audit trail | Process can't start cleanly; surfaced at boot. |
| Local filesystem | Store uploaded CSVs | Upload returns `api_error` if write fails. |

## Stack

> Generic stack rules (model-naming, dev port `:8001`, SQLite-as-production-here, real-key tests) live in `harness/patterns/tech-stack.md`. This is only what **this** project picked, fixed to the boilerplate.

- **Language:** Python 3.12 (backend), TypeScript/React (frontend).
- **Agent framework:** LangGraph — `StateGraph(AgentState)` compiled as `agentic_ai` in `src/graph/agent.py`, entry `src/graph/runner.py::run_agent`.
- **LLM provider + model:** Gemini, default `gemini-3.1-pro` (auto-selected by `LLMClient()` from `AGENT_GEMINI_API_KEY`). Env-configurable via `AGENT_LLM_MODEL`.
- **Backend:** FastAPI (`create_app()` in `src/api/__init__.py`), single origin `:8001`, serving the static UI at `/app/`.
- **Database + ORM:** SQLite via SQLAlchemy 2.0 + Alembic. **SQLite is production here** — gate tests run on SQLite (no PostgreSQL).
- **Frontend:** Next.js 15 static export (`frontend/`, `pnpm build` → `frontend/out/`), React 19, Tailwind.
- **Dependency management:** uv + `pyproject.toml` (Python); pnpm (frontend).

| Key library | Version | Purpose |
|-------------|---------|---------|
| pandas | ≥ 2.2 | Load the full CSV + run generated analysis code locally. |
| numpy | ≥ 1.26 | Backing numeric ops for pandas. |
| plotly | ≥ 5.22 (py) | Backend builds the chart **spec** (Plotly JSON) from the result. |
| react-plotly.js + plotly.js | latest | Frontend renders the interactive chart from the Plotly JSON spec. |
| langgraph | (skeleton-pinned) | Agent graph. |
| sqlalchemy / alembic | 2.0 / latest | ORM + migrations. |
| playwright | latest | Frontend E2E smoke (`frontend/tests/e2e/`). |

> **Assumed:** charting library is **Plotly** (backend emits a Plotly JSON `chart_spec`; frontend renders it with `react-plotly.js`). Chosen over Recharts because the backend can author the full chart spec from the pandas result in one place — the agent decides the chart, the frontend just renders the JSON — keeping chart logic next to the data and out of the UI.

> **Assumed:** the sandbox is a **`subprocess`** running a constrained Python runner (pandas/numpy only in the namespace, no network, hard timeout via `subprocess` `timeout=`), not an in-process `exec`. This isolates a crash/hang in generated code from the API process and makes the timeout enforceable.

**Avoid:** PostgreSQL/psycopg (SQLite is production here); sending any raw data rows to the LLM; in-process `exec()` of generated code without isolation; a hardcoded operation-list interpreter instead of generated code (anti-pattern per `agentic-ai.md#22`); Recharts (we picked Plotly).

## Deployment Model

A long-running local FastAPI process started with `uv run python -m src` from the repo root, serving API + UI on `:8001`. Single-user, single-machine, no auth, no cloud. The CSV files and the SQLite DB live on local disk.

## Local Code-Execution Sandbox (detail)

`src/analyst/sandbox.py` exposes `run_code(csv_paths: dict[str,str], code: str, *, timeout: int) -> SandboxResult`:

- Spawns a **child Python `subprocess`** (`subprocess.run([...], timeout=...)`), passing the generated code and the CSV path(s).
- The child loads the FULL file(s) with `pandas.read_csv` into DataFrame(s) bound to a fixed name (`df`, or named frames for multi-file in Phase 4). The namespace contains only `pd`, `np`, and the DataFrame(s) — no `os`, `open`, `requests`, `import` of network libs.
- The generated code must assign to well-known names: `result` (a value/DataFrame/Series — the answer payload), and optionally `chart` (a dict describing chart type + x/y) and `table` (a DataFrame for the summary). The child serializes `result`/`chart`/`table` to JSON on stdout; the parent reads it back.
- The parent builds the Plotly `chart_spec` JSON from the child's `chart` descriptor + data, coerces `table` to a JSON records list, and captures stdout/stderr.
- **Failure** (exception, non-zero exit, or timeout): the captured traceback/stderr string is returned as the attempt's `error`, fed back into the next `generate_code` call.
- **Privacy invariant:** the child runs locally and its full output is consumed locally; only the *result/chart/table* (already an aggregate the user asked for) is surfaced — and crucially the **LLM is never called from inside the sandbox**. The LLM boundary is in the graph nodes, which receive only schema + sample + question + prior error. See [`spec/agent.md#privacy-boundary`](agent.md#privacy-boundary).
