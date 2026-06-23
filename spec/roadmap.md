# Roadmap

## What This Agent Does

A web-based senior data analyst agent that lets users upload structured datasets (CSV, Excel, JSON), ask natural-language questions about them, and receive rich analytical responses — formatted markdown narrative, sortable data tables, and auto-selected Chart.js charts (bar, line, or pie). The agent translates each question into DuckDB SQL, executes it against the uploaded data, and streams a composed answer back in real time. Every SQL operation is logged for auditability. Sessions persist across page reloads so users can return to prior analyses.

## Who Uses It

Data analysts, business users, and researchers who need to interrogate structured datasets without writing SQL themselves. They upload one or more files, ask questions in plain English, and expect analyst-quality answers with evidence (tables and charts), not just text summaries.

## Core Problem Being Solved

Analysts spend significant time writing ad-hoc SQL queries, formatting results, and producing charts for stakeholders. This agent eliminates that loop: the user describes what they want to know; the agent writes and runs the query, selects an appropriate chart type, and composes a complete response — all while keeping token usage minimal by injecting only schema context (never raw rows) into the LLM prompt.

## Success Criteria

- [ ] A user uploads a CSV and asks a natural-language question; the agent returns a correct SQL-backed answer with a rendered table within 10 seconds.
- [ ] Chart.js charts render correctly for aggregation questions (bar/line/pie auto-selected based on response shape).
- [ ] Sessions persist: refreshing the page restores prior conversation and dataset list.
- [ ] Every SQL query the agent executes appears in the audit log with timestamp, dataset name, SQL text, row count, and latency.
- [ ] The LLM prompt never contains raw dataset rows — only column names, types, and row count.
- [ ] Dataset upload accepts CSV, Excel (.xlsx), and JSON files and makes them immediately queryable.

## What This Agent Does NOT Do (Out of Scope)

- Scheduled or automated reports (no cron, webhooks, or push notifications)
- User authentication or multi-user access control (single-user session model)
- Modifying or writing back to the uploaded datasets
- Connecting to external databases, warehouses, or live APIs
- Natural-language chart customization (chart type is auto-selected, not user-controlled)
- Exporting results to PDF, Excel, or BI tools
- Vector-search or semantic retrieval over dataset content

## Key Constraints

- The LLM prompt must never contain raw dataset rows — schema-only context (column names, types, sample row count) only.
- Every SQL operation logged: timestamp, dataset name, SQL, row count, latency in ms.
- Sessions are persistent across page reloads (SQLite-backed).
- Uploaded datasets stored in `data/uploads/` at repo root; DuckDB reads files directly from disk.
- LLM: `gemini-2.5-flash` via `google-genai` SDK; key is `AGENT_GEMINI_API_KEY` in `.env`.
- Dev port: 8001 (mandatory per harness rules).

---

## Phases of Development

> Phase 1 is the full set of six capabilities, all delivered together as one user-testable increment. Each independent slice builds concurrently; only true dependencies serialize the fan-out.

### Phase 1 — Full Analyst Agent (all six capabilities)

**Goal:** A user opens the web UI, uploads a CSV dataset, types a natural-language question, and receives a streamed response containing markdown text, a sortable data table, and a Chart.js chart — backed by real DuckDB SQL, persisted in a SQLite session, and logged to the audit log. All six capabilities are live on this path.

**Independent slices (parallel build units):**

- `slice-a` (backend-foundation) — SQLite data models (Session, Dataset, Message, QueryLog) + Alembic migration + DuckDB file storage in `data/uploads/` + dataset loader utility (CSV/Excel/JSON → DuckDB view). **deps: none. Must complete before slice-b and slice-c begin.**
- `slice-b` (backend-agent) — LangGraph analyst graph: nodes `classify_intent`, `build_schema_context`, `call_llm_with_tools`, `execute_query`, `format_response`; Gemini tool-use API; DuckDB query execution; audit logging to `QueryLog`. **deps: slice-a (needs models + DuckDB loader).**
- `slice-c` (backend-api) — FastAPI endpoints: sessions CRUD, dataset upload, SSE streaming chat/query endpoint, audit log endpoint; mounts frontend static export. **deps: slice-a + slice-b.**
- `slice-d` (frontend) — Next.js page: session sidebar (list + create + switch), dataset upload panel, chat thread with streaming display, rich response rendering (markdown + sortable table + Chart.js chart), labelled stubs for audit log viewer. **deps: none — builds against API contract in `spec/api.md` concurrently with slice-a/b/c.**

**Declared dependency order:**
```
slice-a  →  slice-b  →  slice-c
slice-d  (independent, runs in parallel with slice-a/b/c)
```

**Key surfaces / files:**

| Slice | Owns |
|-------|------|
| slice-a | `src/db/models.py` (extend), `alembic/versions/0002_analyst.py` (new), `src/db/duckdb_loader.py` (new), `data/uploads/` (directory) |
| slice-b | `src/graph/state.py` (replace), `src/graph/nodes.py` (replace), `src/graph/edges.py` (replace), `src/graph/agent.py` (replace), `src/graph/runner.py` (replace), `src/prompts/analyst.md` (new, replaces transform.md), `src/domain/analyst.py` (new) |
| slice-c | `src/api/sessions.py` (new), `src/api/datasets.py` (new), `src/api/chat.py` (new), `src/api/audit.py` (new), `src/api/__init__.py` (extend to mount new routers), `src/api/runs.py` (replace with stub or remove) |
| slice-d | `frontend/src/app/page.tsx` (replace), `frontend/src/components/SessionSidebar.tsx` (new), `frontend/src/components/DatasetPanel.tsx` (new), `frontend/src/components/ChatThread.tsx` (new), `frontend/src/components/RichResponse.tsx` (new), `frontend/src/components/DataTable.tsx` (new), `frontend/src/components/AnalystChart.tsx` (new), `frontend/src/lib/api.ts` (new), `frontend/package.json` (add chart.js, react-chartjs-2), `pyproject.toml` (add duckdb, openpyxl, python-multipart) |

**Gate command:**
```
uv run alembic upgrade head && uv run pytest tests/phase1/ -q --tb=short
```

Tests in `tests/phase1/` cover: dataset upload + DuckDB load, agent graph end-to-end with real Gemini key, SSE streaming endpoint shape, session persistence round-trip, and audit log record creation. Real `AGENT_GEMINI_API_KEY` must be set in `.env`.

**How the user tests it (handoff seed):**

1. Ensure `.env` contains `AGENT_GEMINI_API_KEY=<real key>` and `AGENT_DATABASE_URL=sqlite:///./data/analyst.db`.
2. Run migrations: `uv run alembic upgrade head`
3. Build the frontend: `cd frontend && pnpm install && pnpm build`
4. Start the server: `uv run python -m src`
5. Open `http://localhost:8001/app/` in a browser.
6. **What you see:** A two-column layout — left sidebar lists sessions (starts empty), right area shows a chat panel with a dataset upload zone at the top.
7. **Test the core path:**
   - Click "New Session" in the sidebar — a new session appears and is selected.
   - Drag a CSV file onto the upload zone (or click "Upload Dataset") — the file name appears in the dataset list below the upload zone with a "Ready" badge.
   - Type a question such as "What are the top 5 rows by [any numeric column]?" and press Enter.
   - Watch the response stream in: first a text narrative, then a sortable table of results, then a bar chart.
8. **Labelled stubs (not bugs):**
   - "Audit Log" tab in the right panel — clicking shows "Audit log coming soon [stub]" placeholder text. This is intentional; the backend logs are written but the UI viewer is a stub.
   - Session rename and delete buttons in the sidebar show a "Not yet implemented" tooltip on hover.
9. **Verify persistence:** Refresh the page — your session and dataset list reappear; the chat history is restored.

### Phase 2 — Audit Log UI + Session Management

**Goal:** Wire the labelled stubs from Phase 1: the audit log viewer shows real query history (SQL, dataset, row count, latency), and session rename/delete work.

**Independent slices (parallel build units):**

- `slice-a` (backend) — audit log read endpoint pagination; session rename (PATCH) and delete (DELETE) endpoints. **deps: Phase 1 slice-c.**
- `slice-b` (frontend) — audit log viewer component (real data, paginated table); session rename inline edit; session delete with confirm dialog. **deps: Phase 1 slice-d API client.**

**Key surfaces / files:**

| Slice | Owns |
|-------|------|
| slice-a | `src/api/audit.py` (extend with pagination), `src/api/sessions.py` (extend with PATCH + DELETE) |
| slice-b | `frontend/src/components/AuditLogViewer.tsx` (new), `frontend/src/components/SessionSidebar.tsx` (extend) |

**Gate command:**
```
uv run pytest tests/phase2/ -q --tb=short
```

**How the user tests it (handoff seed):**

1. Server already running from Phase 1 setup.
2. Open `http://localhost:8001/app/` — click the "Audit Log" tab; it now shows a table of real queries with SQL text, dataset name, row count, and latency.
3. In the sidebar, double-click a session name to rename it; press Enter to save.
4. Click the trash icon on a session; a confirm dialog appears; confirm — the session and its datasets/messages are removed.
