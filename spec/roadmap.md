# Roadmap

## What This Agent Does

A token-economical **senior data analyst** agent. A user uploads a CSV (or Excel) file; the file becomes a real table inside a local SQLite database. The user then asks questions in plain English. The agent emulates a senior data analyst: it writes a **read-only** SQL query against the uploaded table, runs it, and returns a rich, well-written text answer alongside the actual result rows. Work is grouped into **persistent sessions** (one uploaded dataset + its Q&A history) that survive restarts. Every SQL/data operation is recorded in an **audit log**. The agent runs entirely locally — the only thing that leaves the machine is the LLM API call.

## Who Uses It

A single local analyst / operator who has a spreadsheet and wants answers without writing SQL. One user, one machine; no auth, no multi-tenancy.

## Core Problem Being Solved

Replaces the manual loop of "open the spreadsheet → write SQL or a pivot → interpret the numbers → write up the finding." The user asks in English and gets an analyst-grade answer with the supporting rows, without exposing the database to mutation and without sending the data anywhere but the LLM.

## Success Criteria

- [ ] A user can upload a CSV and see it materialized as a queryable table (row count + column list reported back).
- [ ] A natural-language question returns (a) a formatted prose answer and (b) the result rows as a table.
- [ ] No mutation SQL can ever execute — verified by an automated test that asserts an attempted `DELETE`/`DROP`/`UPDATE` is rejected.
- [ ] Every SQL/data operation is persisted to the audit log with timestamp, SQL text, question, session id, rows returned, and success/error.
- [ ] Sessions persist across a server restart — re-opening a session shows its prior Q&A turns.
- [ ] The LLM prompt never contains the full table — only a compact schema summary plus a small sampled set of rows.

## What This Agent Does NOT Do (Out of Scope)

- Charts / visualizations (Phase 2 — shown as a labelled stub in v1).
- Multiple datasets per session and cross-dataset joins (Phase 3 — labelled stub in v1).
- Dashboards and an in-UI audit-log viewer (Phase 4 — labelled stubs in v1).
- Authentication, user accounts, multi-user, sharing.
- Writing/transforming data, scheduled jobs, exports beyond the on-screen result table.
- Non-SQLite warehouses, remote databases.

## Key Constraints

1. **Read-only enforcement** — the agent may only run read queries. Any mutation (INSERT/UPDATE/DELETE/DROP/ALTER/ATTACH/PRAGMA-write/CREATE/REPLACE etc.) is blocked. Enforced by SQL validation AND a read-only DB connection. This is a security boundary.
2. **Strict token economy** — never dump full tables into the prompt. The prompt gets a compact schema summary (column names + types) + a small sampled set of rows (default 5) + the cached session context. Result formatting is also economical.
3. **Full audit log** — persist every SQL/data operation: timestamp, SQL text, rows returned, originating question, session id, success/error.
4. **Local-only** — nothing leaves the machine except the Gemini API call.

## Phases of Development

> **Phase 1 is the smallest first-time-right win.** Its backend is minimal but REAL on the one path; its frontend is visually complete with clearly-labelled NON-FUNCTIONAL stubs for later phases.

### Phase 1 — Upload one CSV → ask → formatted answer + results table

- **Goal:** A user uploads ONE CSV at `/app/`, it becomes a SQLite table, they type a question, and they get a formatted text answer plus a results table. Read-only SQL is enforced, every operation is audit-logged, the session is persisted, and prompting is token-economical (schema summary + sampled rows only). Charts / multiple datasets / dashboards / audit-log viewer appear in the UI as clearly-labelled NON-FUNCTIONAL stubs.
- **Independent slices (parallel build units):**
  - `backend-data` (backend, `src/` only) — deps: none. DB models + Alembic migration for `datasets`, `sessions`, `qa_turns`, `audit_log`; CSV → SQLite table ingestion; schema-summary + row-sampling helpers; the read-only SQL guard; the read-only executor; the audit-log writer. Owns and exposes the interface contract in [api.md](api.md#internal-interface-contract-phase-1).
  - `backend-agent-api` (backend, `src/` only) — **deps: `backend-data`** (TRUE dependency — codes against Slice A's helper signatures in [api.md](api.md#internal-interface-contract-phase-1); must NOT reimplement ingestion/guard/executor/audit). The analyst LangGraph flow (generate-SQL → validate → execute → format), the analyst prompt, the runner, and the FastAPI endpoints.
  - `frontend` (frontend, `frontend/` only) — deps: none. Replace `page.tsx`: upload control, question box, formatted-answer panel, results-table render, and clearly-labelled non-functional stub panels for Charts / Multiple datasets / Dashboards / Audit log.
- **Key surfaces / files:**
  - `backend-data`: `src/db/models.py` (add `DatasetRow`, `SessionRow`, `QaTurnRow`, `AuditLogRow`), `alembic/versions/0002_analyst_tables.py`, `src/data/ingest.py`, `src/data/schema_summary.py`, `src/data/sql_guard.py`, `src/data/executor.py`, `src/data/audit.py`.
  - `backend-agent-api`: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/analyst.md`, `src/api/datasets.py`, `src/api/sessions.py`, `src/api/__init__.py` (router include), `src/domain/analyst.py`.
  - `frontend`: `frontend/src/app/page.tsx`, supporting components under `frontend/src/`.
- **Gate command:**
  ```
  uv run alembic upgrade head && uv run pytest tests/integration/test_analyst_phase1.py tests/unit/test_sql_guard.py -q && cd frontend && pnpm build
  ```
- **How the user tests it (handoff seed):** Build the frontend (`cd frontend && pnpm build`) and start the app (`uv run python -m src`), then open **http://localhost:8001/app/**. Upload a CSV with a few columns (e.g. sales rows). Confirm the UI reports the table was created with its row count and column names. Type *"What is the total revenue by region?"* and submit. Expect a written analyst answer (a few sentences) plus a results table of the actual rows. Restart the server and reload — the prior Q&A turn is still shown for the session. The **Charts, Multiple datasets, Dashboards, and Audit log** panels are visibly labelled "Coming soon (not functional)" — stubs, not bugs.

### Phase 2 — Charts

- **Goal:** Render query results as a chart. Wire the Phase 1 chart stub to real chart rendering of the latest query's result rows.
- **Independent slices (parallel build units):**
  - `backend` (backend) — deps: none. The format node also emits a chart spec hint (chart type + x/y columns); response carries it. No new tables.
  - `frontend` (frontend) — deps: none (renders against the documented chart-spec field). Replace the chart stub with a real chart component.
- **Key surfaces / files:** `src/graph/nodes.py`, `src/domain/analyst.py`, `frontend/src/app/page.tsx` + a chart component.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/integration/test_charts_phase2.py -q && cd frontend && pnpm build`
- **How the user tests it (handoff seed):** Ask an aggregation question; confirm a real chart of the result renders where the Phase 1 stub was.

### Phase 3 — Multiple datasets + cross-dataset joins

- **Goal:** A session holds multiple uploaded datasets; the agent can write read-only SQL that joins across them.
- **Independent slices (parallel build units):**
  - `backend` (backend) — deps: none. Allow N datasets per session; schema-summary spans all session tables; guard/executor unchanged (table-agnostic, already read-only).
  - `frontend` (frontend) — deps: none. Replace the "Multiple datasets" stub with a dataset list + multi-upload control.
- **Key surfaces / files:** `src/data/schema_summary.py`, `src/api/datasets.py`, `frontend/src/app/page.tsx`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/integration/test_multidataset_phase3.py -q && cd frontend && pnpm build`
- **How the user tests it (handoff seed):** Upload two related CSVs into one session; ask a question requiring a join; confirm a correct joined answer.

### Phase 4 — Dashboards + audit-log viewer

- **Goal:** Saved multi-question dashboards plus an in-UI audit-log viewer over the `audit_log` table.
- **Independent slices (parallel build units):**
  - `backend` (backend) — deps: none. `GET /audit` (paginated read of `audit_log`); a `dashboards` table + save/list endpoints.
  - `frontend` (frontend) — deps: none. Replace the Dashboards and Audit-log stubs with real views.
- **Key surfaces / files:** `src/api/audit.py`, `src/api/dashboards.py`, `alembic/versions/0003_dashboards.py`, `frontend/src/app/page.tsx`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/integration/test_dashboards_phase4.py -q && cd frontend && pnpm build`
- **How the user tests it (handoff seed):** Open the Audit-log view and see prior operations; build and re-open a saved dashboard of several questions.
