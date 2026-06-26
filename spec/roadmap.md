# Roadmap

## What This Agent Does

A data-analysis agent that accepts a CSV file upload, loads it into a local SQLite table, and lets the user ask natural-language questions about the data via a web chat interface. For each question the agent runs a five-node LangGraph pipeline: it introspects the table schema, generates a safe SELECT query with Gemini, executes the query, selects the right chart type, and writes a plain-English insight. Every answer shows the SQL that was run, an interactive Recharts chart, and a one-paragraph insight summary. Every graph node is traced end-to-end through LangSmith.

## Who Uses It

Data analysts, business stakeholders, and technical users who have a CSV and want fast answers without writing SQL or configuring a BI tool. They upload once and ask many questions in a chat-style panel.

## Core Problem Being Solved

Users with CSV data spend time hand-writing SQL or wrangling pivot tables to answer ad-hoc questions. This agent removes that friction: one upload, then natural-language questions that return charts, SQL, and plain-English insight in seconds.

## Success Criteria

- [ ] A user can upload any well-formed CSV and receive a `session_id` plus a column schema preview within 3 seconds.
- [ ] A natural-language question over the uploaded data returns a valid SELECT query, a rendered Recharts chart, and an insight paragraph within 15 seconds.
- [ ] SQL safety guardrails block every INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, and TRUNCATE — confirmed by automated tests that attempt each forbidden keyword.
- [ ] Every graph node entry/exit and every LLM call appears as a trace span in LangSmith when `LANGCHAIN_TRACING_V2=true`.
- [ ] The backend returns a structured error (not a 500 crash) when the CSV is malformed, the query returns zero rows, or Gemini refuses to generate SQL.

## What This Agent Does NOT Do (Out of Scope)

- Multi-file joins across more than one uploaded CSV.
- User authentication or per-user data isolation.
- Saving or "pinning" charts to a dashboard.
- Writing back to the CSV or any mutating SQL operation.
- Ingesting data from cloud databases, S3, or URLs — only local file upload.
- Asynchronous / long-poll query execution — the HTTP response is synchronous.
- Streaming token output from Gemini to the browser.

## Key Constraints

- SQLite is the only database; `data/agent.db` for persistent session metadata; per-upload dynamic tables live in the same file.
- All SQL execution is read-only. DDL/DML is blocked at the execution node, not just by prompt.
- LLM provider: Gemini via `langchain-google-genai` so LangSmith traces LLM calls automatically.
- Default model: `gemini-2.5-flash` (configurable via `AGENT_LLM_MODEL`).
- LangSmith tracing requires `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_PROJECT` in `.env`.
- Dev port: 8001.
- Frontend: static export (`output: 'export'`, `basePath: '/app'`) served by FastAPI at `/app`; single-origin run path.

---

## Phases of Development

> Phase 1 is the smallest first-time-right user-testable win. Its backend is minimal but REAL on the one core path. Its frontend is visually complete: real UI for the working path PLUS clearly-labelled non-functional stubs for later phases.

---

### Phase 1 — CSV Upload + NL Query (First Win)

- **Goal:** A user uploads a CSV, asks one natural-language question, and receives the SQL query, a rendered Recharts chart, and an insight paragraph — end-to-end against the real Gemini API, with LangSmith traces captured.

- **Independent slices (parallel build units):**
  - `slice-a` (backend) — rewires the entire `src/` skeleton for data-analysis: new AgentState, five graph nodes, SQLite CSV loader, upload and query API endpoints, updated domain models and DB models, Gemini via `langchain-google-genai`, LangSmith env wiring, SQL safety guardrails, structlog observability, unit + integration tests. **deps: none**
  - `slice-b` (frontend) — replaces `frontend/src/app/page.tsx` with the two-panel CSV-upload + chat UI, adds `recharts` dependency, implements real upload flow and real query/answer panel (SQL code block, Recharts chart, insight text). Stubs for dashboard pinning, multi-file joins, and auth are present as clearly-labelled disabled elements. **deps: none**

- **Key surfaces / files:**
  - `slice-a` owns (disjoint from frontend):
    - `src/graph/state.py`
    - `src/graph/nodes.py`
    - `src/graph/edges.py`
    - `src/graph/agent.py`
    - `src/graph/runner.py`
    - `src/api/upload.py` (new file)
    - `src/api/query.py` (new file)
    - `src/api/runs.py` (replaced — re-exports or removed)
    - `src/api/__init__.py` (router registration updated)
    - `src/domain/run.py` (replaced with upload + query domain models)
    - `src/db/models.py` (add UploadSession, QueryRun; keep/remove RunRow)
    - `src/config/settings.py` (add `langchain_api_key`, `langchain_tracing_v2`, `langchain_project`, `llm_model` default `gemini-2.5-flash`)
    - `src/prompts/transform.md` (replaced with SQL-generation system prompt)
    - `tests/conftest.py` (update for new models)
    - `tests/unit/test_sql_safety.py`
    - `tests/unit/test_csv_loader.py`
    - `tests/integration/test_upload.py`
    - `tests/integration/test_query_pipeline.py`
    - `tests/e2e/test_full_flow.py`
  - `slice-b` owns (disjoint from backend):
    - `frontend/src/app/page.tsx`
    - `frontend/src/app/layout.tsx`
    - `frontend/src/components/UploadPanel.tsx`
    - `frontend/src/components/ChatPanel.tsx`
    - `frontend/src/components/AnswerCard.tsx`
    - `frontend/src/components/StubBadge.tsx`
    - `frontend/package.json` (add `recharts`, `@types/recharts`)

- **Gate command:**
  ```
  uv run pytest tests/ -x -q
  ```
  Run from repo root. Requires `.env` with `AGENT_GEMINI_API_KEY`, `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_PROJECT`. Tests call the real Gemini API and write to a temp SQLite DB.

- **How the user tests it (handoff seed):**
  1. `cd frontend && pnpm install && pnpm build` — builds static export to `frontend/out/`
  2. `uv run python -m src` — starts FastAPI at `http://localhost:8001`
  3. Open `http://localhost:8001/app/` (trailing slash required)
  4. **Upload screen (REAL):** drag or pick any CSV file → click "Upload" → see table name + column list appear below the button
  5. **Chat screen (REAL):** type a question (e.g. "What are the top 5 values by count?") → click "Ask" → within ~15 s see three panels: SQL code block, Recharts bar/line chart, insight paragraph
  6. **Stubs (labelled, non-functional):** "Pin to Dashboard" button (grey, tooltip "Coming in Phase 2") · "Join another file" link (grey, tooltip "Coming in Phase 3") · "Sign in" link (grey, tooltip "Coming in Phase 3")
  7. **LangSmith:** open the LangSmith project — confirm a trace with five spans (schema_introspection, sql_generation, sql_execution, chart_selection, insight_generation) appears.

- **Cross-cutting Definition of Done (every slice):**
  README delta (applied serially after the parallel slices land) · a structured log line per new operation (node entry/exit, LLM call, CSV load, SQL execution) · error handling + timeout on each new external call (Gemini API, SQLite execution) · a real behaviour-asserting test (shape + content assertions on real Gemini responses) · an incremental drift check — see `harness/patterns/phases.md` Horizontal Axis.

---

### Phase 2 — Dashboard Pinning

- **Goal:** A user can pin any answer card to a personal dashboard tab that persists across page reloads. The pinned view shows the chart and insight re-rendered from stored `chart_spec` JSON, without re-running the query.

- **Independent slices (parallel build units):**
  - `slice-a` (backend) — `GET /sessions/{session_id}/pins` and `POST /sessions/{session_id}/pins` endpoints reading from `QueryRun` rows marked `pinned=true`. Add `pinned` boolean column via Alembic migration. **deps: none**
  - `slice-b` (frontend) — wire the "Pin to Dashboard" button to the new endpoint; render a `/dashboard` route that lists pinned cards with stored chart specs. **deps: none**

- **Key surfaces / files:**
  - `slice-a`: `src/api/pins.py`, `src/api/__init__.py`, Alembic migration file, `tests/integration/test_pins.py`
  - `slice-b`: `frontend/src/app/dashboard/page.tsx`, `frontend/src/components/PinnedCard.tsx`, `frontend/src/components/AnswerCard.tsx` (add pin button wiring)

- **Gate command:**
  ```
  uv run pytest tests/integration/test_pins.py -x -q
  ```

- **How the user tests it (handoff seed):**
  1. Upload a CSV and ask a question as in Phase 1.
  2. Click "Pin to Dashboard" on an answer card → button turns blue → count badge on Dashboard tab increments.
  3. Click "Dashboard" tab → see pinned chart and insight, re-rendered from stored spec without a new LLM call.
  4. Reload the page → pinned card persists.

- **Cross-cutting Definition of Done (every slice):** README delta (applied serially) · structured log line per new operation (pin write, pin list read) · error handling on DB writes · a real behaviour-asserting test · incremental drift check.

---

### Phase 3 — Multi-File Joins

- **Goal:** A user can upload a second CSV in the same session and ask questions that join across both tables. The SQL-generation node receives the schema of all tables in the session.

- **Independent slices (parallel build units):**
  - `slice-a` (backend) — `UploadSession` extended to track multiple tables per session; `schema_introspection` node reads all session tables; SQL-generation prompt updated to include all schemas. **deps: none**
  - `slice-b` (frontend) — wire the "Join another file" stub into a real multi-upload panel showing both schemas. **deps: none**

- **Key surfaces / files:**
  - `slice-a`: `src/db/models.py`, `src/graph/nodes.py` (schema node), `src/prompts/transform.md`, Alembic migration, `tests/integration/test_multi_table.py`
  - `slice-b`: `frontend/src/components/UploadPanel.tsx` (multi-file), `frontend/src/app/page.tsx`

- **Gate command:**
  ```
  uv run pytest tests/integration/test_multi_table.py -x -q
  ```

- **How the user tests it (handoff seed):**
  1. Upload a first CSV → see schema A.
  2. Click "Join another file" → upload a second CSV → see schema A + B.
  3. Ask a join question (e.g. "Join orders to customers and show total spend by region") → receive SQL with a JOIN, a chart, and an insight.

- **Cross-cutting Definition of Done (every slice):** README delta (applied serially) · structured log line per new table loaded · error handling on second upload and join SQL · a real behaviour-asserting test · incremental drift check.
