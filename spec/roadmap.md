# Roadmap

---

## What This Agent Does

A local-first data-analyst agent. A user uploads a dataset (CSV in v1), the file becomes a real queryable table inside the local SQLite database, and the user asks questions in plain English. The agent translates each question into SQL (text-to-SQL via the LLM), runs that SQL locally against the dataset, and returns a rich, formatted answer — explanatory text plus a data table. Every data operation (the ingest and each query) is recorded in a full audit trail, and the uploaded dataset plus the conversation/query history persist across page reloads. The product emulates the workflow of a senior data analyst while keeping LLM token usage tightly economical: the model only ever sees a table's schema, a tiny row sample, and query result sets — never the full dataset.

## Who Uses It

Analysts, founders, operators, and data-curious people who have a spreadsheet/CSV and questions about it but do not want to write SQL or hand their data to a cloud service. They want senior-analyst-quality answers locally, fast, and auditable. Their goal: ask a question, get a trustworthy formatted answer, and be able to see exactly what SQL ran.

## Core Problem Being Solved

Answering questions about a dataset today means either writing SQL/spreadsheet formulas by hand, or pasting data into a cloud LLM (expensive in tokens, and the data leaves the machine, with no record of what actually ran). This agent removes the SQL skill barrier, keeps all data local, stays cheap on tokens (schema + sample + result only), and logs every operation so the analysis is fully auditable.

## Success Criteria

- [ ] A user can upload a single CSV and it becomes a real, queryable SQLite table with correct column names and inferred types.
- [ ] A natural-language question returns a correct answer rendered as formatted text plus a data table, using SQL the LLM generated.
- [ ] The LLM prompt for a query never contains full dataset rows — only schema, a sample of ≤ 20 rows, and (for the answer step) the result set.
- [ ] Every ingest and every query writes an audit entry (timestamp, exact SQL, row count, column names, duration, success/error) that is viewable in the UI.
- [ ] After a page reload, the previously uploaded dataset and the full query history are still present (re-fetched from SQLite).

## What This Agent Does NOT Do (Out of Scope)

- No cloud storage, no multi-user accounts, no auth — single local user only.
- No data leaves the machine except the LLM prompt (schema + sample + results).
- v1 ingest is CSV only — no Excel, JSON, Parquet, or database connectors (Excel is Phase 2+).
- v1 is single-dataset per query — no cross-dataset joins (Phase 2).
- No charts, dashboards, or multi-step analyst planning in v1 (Phases 3–5).
- The agent only issues read-only `SELECT` queries against dataset tables — never `INSERT`/`UPDATE`/`DELETE`/`DROP`/`ATTACH`/`PRAGMA`.
- No write-back / export of modified data.

## Key Constraints

- **Token economy is a hard requirement.** The LLM reasons over small inputs only (schema + ≤ 20-row sample + result set). Full dataset rows are NEVER sent. Schemas are cached. See [`agent.md`](agent.md).
- **Local-only.** SQLite + local files. Nothing is sent off-machine except the LLM prompt.
- **Full audit trail.** Every SQL/data operation is logged as a first-class entity with a read API + UI panel. See [`capabilities/audit-trail.md`](capabilities/audit-trail.md).
- **Read-only SQL sandbox.** Generated SQL must be a single `SELECT` and is validated + executed read-only. See [`architecture.md`](architecture.md).
- **Use the existing skeleton in place** (flat `src/` package, FastAPI + LangGraph + SQLite + Next.js static export, Gemini via `LLMClient`). See [`architecture.md` → `## Stack`](architecture.md).

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Backend is minimal but REAL on the one core path (CSV → table → NL query → answer + audit, persisted). Frontend is visually complete: real UI for that path PLUS clearly-labelled non-functional stubs for the deferred vision.

### Phase 1 — Upload a CSV, ask a question, get an audited answer

- **Goal:** A user opens the app, uploads ONE CSV, asks a question in plain English, and gets back formatted text + a data table produced by LLM-generated SQL run locally. Both the ingest and the query appear in an audit panel. Reloading the page restores the dataset and the full query history.
- **Independent slices (parallel build units):**
  - `backend` (backend) — the entire `src/` data-analyst path: ORM models + migration for datasets / queries / audit_log; CSV ingest (CSV → `ds_<id>` table + schema cache); the LangGraph text-to-SQL flow (replace `transform_text` slot); read-only SQL sandbox + executor; the new routers (`datasets`, `queries`, `audit`); tests. **Deps: none.**
  - `frontend` (frontend) — the full single-page data-analyst UI in `frontend/src/`: upload control, ask box, answer (formatted text + table), audit panel, session-restore on load, and the LABELLED "Coming soon" stubs (multi-dataset manager, charts, dashboards, senior-analyst workflow). Fetches same-origin `/datasets`, `/queries`, `/audit`. **Deps: none** — builds against the API contract in [`api.md`](api.md); no shared files with `backend`.
- **Key surfaces / files:**
  - `backend`: `src/db/models.py`, `alembic/versions/0002_data_analyst.py`, `src/ingest/csv_loader.py` (new), `src/graph/{state,nodes,edges,agent,runner}.py` (replace transform logic in place), `src/sql/sandbox.py` (new), `src/prompts/text_to_sql.md` + `src/prompts/answer.md` (replace `transform.md`), `src/api/{datasets,queries,audit}.py` (new; repurpose/replace `src/api/runs.py`), `src/api/__init__.py` (register routers), `src/domain/*` (request/response models), `tests/`.
  - `frontend`: `frontend/src/app/page.tsx` (replace transform form), any `frontend/src/components/*` it adds, `frontend/src/lib/api.ts` (new fetch helpers).
- **Gate command:** from repo root — `uv run alembic upgrade head && uv run pytest && (cd frontend && pnpm build)`
  - Tests run against the real Gemini API via `.env` (`AGENT_GEMINI_API_KEY`) and the production SQLite driver. `pnpm build` must produce `frontend/out/` with real Tailwind utility classes (not a barebones build).
- **How the user tests it (handoff seed):**
  1. From repo root: `uv run alembic upgrade head`, then `cd frontend && pnpm build`, then back at repo root `uv run python -m src`.
  2. Open **`http://localhost:8001/app/`** (note port `8001`, the `/app/`, trailing slash).
  3. Upload a small CSV (e.g. a sales export). Expect: a confirmation showing the table name, row count, and detected columns; an audit entry appears for the ingest.
  4. Type a question (e.g. "What is the total revenue by region?") and submit. Expect: formatted text answer plus a data table of the result; a second audit entry showing the exact generated SQL, row count, columns, and duration.
  5. Open the Audit panel — both operations are listed with timestamps and SQL.
  6. Reload the page. Expect: the dataset is still selected and the previous question + answer + audit history are all still shown (re-fetched from SQLite).
  - **Real on the tested path:** upload, ask, answer text + table, audit panel, session restore.
  - **Labelled stubs ("Coming soon", non-functional):** multi-dataset manager / dataset switcher, charts toggle, dashboards tab, "senior analyst mode" workflow toggle. These are visible to convey the vision and must never be mistaken for bugs.

### Phase 2 — Multiple datasets + cross-dataset NL queries

- **Goal:** A user manages several datasets (upload, name, list, delete, switch) and asks questions that span more than one dataset (NL joins). Wires the Phase-1 "multi-dataset manager" stub into reality.
- **Independent slices (parallel build units):**
  - `backend` (backend) — dataset management endpoints (list/rename/delete), multi-table schema assembly for the text-to-SQL prompt (include the schemas + samples of all active datasets), join-aware SQL generation + sandbox validation across multiple `ds_<id>` tables; tests. **Deps: none** (extends Phase-1 backend).
  - `frontend` (frontend) — real multi-dataset manager (list, select multiple as "active", rename, delete) replacing the stub; query box scoped to the active dataset set. **Deps: none** (builds to updated `api.md`).
- **Key surfaces / files:** `backend`: `src/api/datasets.py`, `src/ingest/csv_loader.py`, `src/graph/nodes.py` (schema-assembly + SQL gen), `src/sql/sandbox.py`, tests. `frontend`: `frontend/src/app/page.tsx`, `frontend/src/components/*`.
- **Gate command:** from repo root — `uv run alembic upgrade head && uv run pytest && (cd frontend && pnpm build)`
- **How the user tests it (handoff seed):** Run as Phase 1. Upload two CSVs, mark both active, ask a question that requires both (e.g. "Average order value per customer segment, joined to the segments table"); expect a correct joined answer + table; audit shows the multi-table SELECT. Rename and delete a dataset; expect the list to update and reload to persist.

### Phase 3 — Charts

- **Goal:** When a result is chartable, the user can render it as a chart (bar/line/pie). Wires the Phase-1 "charts" stub into reality.
- **Independent slices:**
  - `backend` (backend) — a chart-spec step: the LLM proposes a chart type + axis mapping from the result schema (small input only); endpoint/field returns a chart spec alongside the table. **Deps: none.**
  - `frontend` (frontend) — chart rendering (client charting lib) driven by the chart spec, with a table/chart toggle. **Deps: none.**
- **Key surfaces / files:** `backend`: `src/graph/nodes.py`, `src/prompts/chart_spec.md` (new), `src/api/queries.py`. `frontend`: chart component in `frontend/src/components/`.
- **Gate command:** from repo root — `uv run alembic upgrade head && uv run pytest && (cd frontend && pnpm build)`
- **How the user tests it:** Ask an aggregation question, toggle to chart view, confirm a correct chart renders.

### Phase 4 — Dashboards

- **Goal:** The user pins answers/charts to a saved dashboard that persists and reloads. Wires the Phase-1 "dashboards" stub into reality.
- **Independent slices:**
  - `backend` (backend) — `dashboard` + `dashboard_item` ORM tables, migration, CRUD endpoints to pin/unpin saved query results. **Deps: none.**
  - `frontend` (frontend) — dashboard tab: grid of pinned items, add/remove, persisted across reload. **Deps: none.**
- **Gate command:** from repo root — `uv run alembic upgrade head && uv run pytest && (cd frontend && pnpm build)`
- **How the user tests it:** Pin two answers to a dashboard, reload, confirm they persist on the dashboard tab.

### Phase 5 — Senior-analyst workflow (multi-step planning)

- **Goal:** For complex questions the agent plans multiple analytical steps (explore → query → refine → synthesize) and narrates its reasoning, emulating a senior analyst. Wires the Phase-1 "senior analyst mode" stub into reality.
- **Independent slices:**
  - `backend` (backend) — add a Planning + Reflection loop to the graph (plan steps, run each as a text-to-SQL sub-query, synthesize), still token-economical (each step sees only schema/sample/result). **Deps: none.**
  - `frontend` (frontend) — render the multi-step plan + per-step results + final synthesis; mode toggle made real. **Deps: none.**
- **Gate command:** from repo root — `uv run alembic upgrade head && uv run pytest && (cd frontend && pnpm build)`
- **How the user tests it:** Enable analyst mode, ask an open-ended question (e.g. "What's driving the revenue drop?"), confirm a stepwise plan, intermediate queries (all audited), and a synthesized conclusion.
