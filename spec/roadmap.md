# Roadmap

## What This Agent Does

The personal data analysis agent lets a solo user upload a CSV file, ask questions about the data in plain English, and immediately see an answer plus an interactive chart — all in a local browser UI, with no data leaving the machine (only a schema summary goes to Gemini). The agent handles the full analysis pipeline: parsing the file, planning what computation to run, executing it with pandas, writing a plain-English narration, and generating a Plotly chart spec rendered by the browser. In later phases it also connects to local SQL databases (SQLite, Postgres, MySQL) and supports multi-turn conversation per dataset.

## Who Uses It

A single technical user who does exploratory data analysis locally — a data analyst, developer, or researcher who has CSV exports or local databases they want to query without writing code or leaving their machine. They open a browser tab, upload a file, and type questions.

## Core Problem Being Solved

Querying CSV files and local databases currently requires either writing code (pandas, SQL) or uploading data to a cloud service. This agent removes both barriers: the user asks questions in plain English, and all data stays local. The LLM handles the analysis planning; pandas handles the computation; the result is immediately displayed as text + chart.

## Success Criteria

- [ ] A user can upload a CSV and get a correct plain-English answer to a numerical question (e.g., "What is the average revenue by region?") with a chart, all within a single browser session, in under 20 seconds.
- [ ] The answer is correct: for a CSV with known values, the answer matches the true computed result within ±1%.
- [ ] No CSV row data is transmitted to the Gemini API — only the schema summary (column names, dtypes, shape, ≤5 sample rows) and the computed result are sent.
- [ ] A failed Gemini call (e.g., network error) surfaces a readable error message in the browser; the app does not crash and does not return a 5xx.
- [ ] The full analysis pipeline (upload → question → answer + chart) is covered by automated tests that run against the real Gemini API using keys from `.env`.

## What This Agent Does NOT Do (Out of Scope)

- Multi-user access, authentication, or authorization — personal use only.
- Cloud storage or any remote database — all data is local.
- Excel, Parquet, or other file formats in Phase 1 — CSV only.
- Writing or modifying data — the agent is read-only.
- Scheduling, background jobs, or webhooks — on-demand only.
- Exporting reports to PDF or email — not planned.
- Learning or adapting from user feedback — no fine-tuning loop.

## Key Constraints

- All user data (CSV files, query results) stays on the local filesystem and SQLite database; only schema summaries and computed results are sent to Gemini.
- LLM costs must be kept low: use `gemini-2.5-flash`, concise prompts, and cap context passed to the LLM.
- Phase 1 must work the first time the user tests it — zero rough edges on the tested path.
- The existing skeleton structure (`src/api/`, `src/graph/`, `src/db/`, etc.) is extended in place; no renames or restructuring.

---

## Phases of Development

### Phase 1 — CSV Upload + Analysis + Charts

- **Goal:** Upload a CSV file, ask a natural-language question, and get a plain-English answer plus an interactive Plotly chart in the browser. The complete primary user journey, end-to-end and working the first time.

- **Independent slices (parallel build units):**

  - `slice-a` (backend) — Replace the skeleton's `transform_text` graph with the 6-node analysis graph; add pandas CSV parsing; add Plotly chart generation; add `DatasetRow` and `AnalysisRow` DB models; add Alembic migration; add new API routes (`POST /datasets`, `POST /analyses`, `GET /datasets`, `GET /analyses/{id}`); wire Gemini for plan + answer LLM calls; write integration tests covering the full pipeline. deps: none.

  - `slice-b` (frontend) — Replace the skeleton's transform form with: CSV file upload component (drag-and-drop + click-to-browse), question input field, "Analyze" button, plain-English answer display, embedded Plotly chart render via Plotly.js, loading state, and error display. Add labelled stub UI for "Connect Database" (Phase 2). deps: none (API contract is fixed in `spec/architecture.md` and both slices build independently against it).

- **Key surfaces / files:**

  Slice A (backend — `src/` only, never `frontend/`):
  - `src/graph/state.py` — new `AgentState` fields
  - `src/graph/nodes.py` — replace `transform_text`; add `ingest_csv`, `plan_analysis`, `execute_analysis`, `generate_answer`, `generate_chart`, `finalize`, `handle_error`
  - `src/graph/edges.py` — replace `after_transform`; add `after_ingest`, `after_plan`, `after_execute`, `after_answer`, `after_chart`
  - `src/graph/agent.py` — rebuild graph with 7 nodes per `spec/agent.md`
  - `src/graph/runner.py` — replace `run_agent`; add `run_analysis(dataset_id, question) -> dict`
  - `src/db/models.py` — add `DatasetRow`, `AnalysisRow` (keep `RunRow` for backward compat)
  - `src/api/datasets.py` — new file: `POST /datasets`, `GET /datasets`
  - `src/api/analyses.py` — new file: `POST /analyses`, `GET /analyses/{id}`
  - `src/api/__init__.py` — register new routers; keep existing `health` and `runs` routers
  - `src/domain/dataset.py` — new file: `DatasetUploadResponse`, `DatasetListItem`
  - `src/domain/analysis.py` — new file: `AnalysisRequest`, `AnalysisResponse`
  - `src/prompts/analysis_plan.md` — new file: system prompt for plan_analysis node
  - `src/prompts/answer.md` — new file: system prompt for generate_answer node
  - `alembic/versions/0002_datasets_and_analyses.py` — new migration adding `datasets` and `analyses` tables
  - `pyproject.toml` — add `pandas>=2.2`, `plotly>=5.22`, `python-multipart>=0.0.9`
  - `tests/integration/test_analysis_pipeline.py` — new: full pipeline integration tests
  - `tests/unit/test_nodes.py` — new: unit tests for node logic (with mocked LLM)

  Slice B (frontend — `frontend/` only, never `src/`):
  - `frontend/src/app/page.tsx` — replace transform form with analysis UI
  - `frontend/src/app/components/CsvUpload.tsx` — new: file upload component
  - `frontend/src/app/components/AnalysisResult.tsx` — new: answer + chart display
  - `frontend/src/app/components/PlotlyChart.tsx` — new: Plotly.js chart renderer
  - `frontend/src/app/globals.css` — update if needed
  - `frontend/package.json` — add `plotly.js-dist-min` and `@types/plotly.js`
  - `frontend/pnpm-lock.yaml` — updated by pnpm

- **Gate command** (run from repo root; requires `AGENT_GEMINI_API_KEY` in `.env`):
  ```
  uv run alembic upgrade head && uv run pytest tests/ -v
  ```
  The integration tests in `tests/integration/test_analysis_pipeline.py` call the real Gemini API and assert on a test CSV with known values (>100 rows so sample ≠ full). The unit tests in `tests/unit/test_nodes.py` mock the LLM and assert on node logic directly. All tests use the SQLite driver (production driver for this tool).

- **How the user tests it (handoff):**
  1. Ensure `AGENT_GEMINI_API_KEY` is set in `.env`.
  2. Run: `cd frontend && pnpm install && pnpm build && cd .. && uv run alembic upgrade head && uv run python -m src`
  3. Open `http://localhost:8001/app/` in a browser.
  4. **Real path:** Drag a CSV file onto the upload area (or click to browse). The filename and row count appear. Type a question like "What is the average value per category?" and click "Analyze". Within ~10 seconds, a plain-English answer appears and a Plotly bar chart renders below it.
  5. **Labelled stub:** A "Connect Database" button in the sidebar is visibly labelled "Coming in Phase 2 — not yet functional" and is disabled. It is never mistaken for a bug.
  6. Expected: answer is factually consistent with the CSV data; chart renders with correct axes; no errors in the browser console.

---

### Phase 2 — SQL Database Connectivity

- **Goal:** Connect to a local SQLite, PostgreSQL, or MySQL database by URL, browse its tables, and ask natural-language questions answered by generated SQL.

- **Independent slices (parallel build units):**
  - `slice-a` (backend) — Add `connections` table and `ConnectionRow` model; add `POST /connections`, `GET /connections`, `POST /connections/{id}/refresh` routes; add `inspect_schema`, `generate_sql`, `execute_sql` graph nodes; extend `AgentState` with `connection_id`, `db_url`, `sql_query`, `query_results`; add SQL dialect routing (SQLite / Postgres / MySQL via SQLAlchemy URL scheme); add Alembic migration. deps: none.
  - `slice-b` (frontend) — Wire the "Connect Database" stub into a real connection form (URL input, connect button, table browser); add a query tab alongside the CSV tab; render SQL query in a code block alongside the answer. deps: none.

- **Key surfaces / files:**
  - `src/api/connections.py`, `src/domain/connection.py`, `src/db/models.py` (add `ConnectionRow`), `src/graph/nodes.py` (add SQL nodes), `src/graph/state.py` (add SQL fields), `src/graph/agent.py` (route by mode: csv vs. sql), `alembic/versions/0003_connections.py`
  - `frontend/src/app/components/DbConnect.tsx`, `frontend/src/app/components/QueryResult.tsx`, `frontend/src/app/page.tsx` (tab switching)

- **Gate command:**
  ```
  uv run pytest tests/ -v
  ```
  Integration test uses a test SQLite DB with known data; asserts correct SQL is generated and executed; asserts SELECT-only enforcement.

- **How the user tests it:** Open `http://localhost:8001/app/`, click "Connect Database", enter a SQLite URL (e.g., `sqlite:///./data/mydb.sqlite`), see the table list, type "How many rows are in the orders table?", see a correct answer with the generated SQL shown.

---

### Phase 3 — Agentic Stack Upgrade + Multi-Turn Conversation

- **Goal:** Multi-turn conversation per dataset (ask follow-up questions in context); reflection loop for plan quality; hardened error handling with retries and timeouts.

- **Independent slices (parallel build units):**
  - `slice-a` (backend) — Add conversation history to `AgentState` (list of `{question, answer}` turns); wire LangGraph checkpointing (SqliteSaver); add `reflect_plan` node that critiques the analysis plan and re-plans if quality is low; add retry + timeout wrappers around all Gemini calls; add `conversation_id` to `analyses` table.
  - `slice-b` (frontend) — Show conversation thread (prior Q&A pairs per dataset session); "Ask a follow-up" input; scroll to latest answer.

- **Key surfaces / files:** `src/graph/state.py` (add `conversation_history`, `conversation_id`), `src/graph/nodes.py` (add `reflect_plan`), `src/graph/agent.py` (add reflection edge), `src/graph/runner.py` (SqliteSaver checkpointer), `alembic/versions/0004_conversation.py`, `frontend/src/app/components/ConversationThread.tsx`

- **Gate command:**
  ```
  uv run pytest tests/ -v
  ```
  Tests exercise reflection loop (plan rejected once → re-planned → analysis succeeds); multi-turn state preserved across two `POST /analyses` calls with same `conversation_id`; retry on simulated Gemini timeout.

- **How the user tests it:** Upload a CSV, ask a question, see the answer. Ask a follow-up question that references the first answer (e.g., "Which of those regions grew the most?"). See a contextually correct answer that accounts for prior turns.

---

### Phase 4 — Complete Agentic System

- **Goal:** No stubs anywhere. Full end-to-end: CSV and SQL both real and tested; multi-turn conversation; all spec capabilities implemented; spec-to-code drift audit clean.

- **Independent slices (parallel build units):**
  - `slice-a` (backend) — Close any remaining gaps between `spec/agent.md` graph and running code; ensure all `spec/capabilities/` success criteria pass; run drift audit.
  - `slice-b` (frontend) — Final UI polish: dataset history sidebar (list prior uploads with timestamps), analysis history per dataset, copy-answer button, chart download button.

- **Key surfaces / files:** Any remaining gaps identified by the drift audit.

- **Gate command:**
  ```
  uv run pytest tests/ -v
  ```
  Every success criterion in `spec/capabilities/csv_analysis.md` and `spec/capabilities/sql_connectivity.md` is covered by a test. Drift audit (`qa-auditor`) confirms `spec/agent.md` graph matches running `src/graph/agent.py`.

- **How the user tests it:** Full end-to-end: upload a CSV, ask three follow-up questions in sequence, connect to a local SQLite DB, ask a SQL question, confirm conversation history is preserved across both modes.
