# Architecture

## System Overview

The analyst agent is a single-origin web application: a FastAPI backend (port 8001) serves both the REST/SSE API and the statically-exported Next.js frontend (mounted at `/app`). The user's browser is the only client. When the user asks a question, a LangGraph agent translates it into DuckDB SQL, executes the query against uploaded dataset files, logs the operation, and streams a rich response (markdown text + table rows + chart spec) back over Server-Sent Events.

## Component Map

```
Browser
  │
  │  GET /app/*          (static Next.js export)
  │  POST /sessions      (REST)
  │  POST /datasets      (multipart upload)
  │  GET  /chat          (SSE stream)
  │  GET  /audit         (REST)
  ▼
FastAPI  (port 8001)
  ├── StaticFiles → frontend/out/
  ├── SessionsRouter
  ├── DatasetsRouter
  ├── ChatRouter  ─────────────────────► LangGraph Analyst Graph
  └── AuditRouter                              │
                                               ├── build_schema_context  → SQLite (datasets metadata)
                                               ├── call_llm_with_tools   → Gemini 2.5 Flash
                                               └── execute_query         → DuckDB (data/uploads/)
                                                        │
                                                        └── audit log → SQLite (query_logs)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| Frontend (Next.js) | Session sidebar, dataset upload panel, SSE chat thread, rich response rendering (markdown + sortable table + Chart.js chart) |
| API (FastAPI) | REST endpoints for sessions/datasets/audit; SSE endpoint for streaming chat; mounts static frontend |
| Agent Graph (LangGraph) | Classify intent, build schema context, call Gemini with tool-use, execute DuckDB query, format rich response |
| LLM (Gemini 2.5 Flash) | Translate natural-language question + schema context into a SQL tool call |
| Analytical Engine (DuckDB) | In-process SQL execution against uploaded CSV/Excel/JSON files |
| Metadata Store (SQLite) | Persist sessions, dataset records, messages, and query audit log |
| Filesystem | Raw uploaded files at `data/uploads/<session_id>/` |

## Data Flow

1. **Trigger:** User types a natural-language question in the chat input and presses Enter.
2. Frontend opens a Server-Sent Events connection to `GET /chat?session_id=<id>&q=<question>`.
3. FastAPI invokes `run_analyst(session_id, question)` as a streaming generator.
4. LangGraph executes the analyst graph:
   - `classify_intent`: determine if this is a data query, clarification, or off-topic.
   - `build_schema_context`: load dataset column names, types, and row count from SQLite; assemble compact schema string — no raw rows.
   - `call_llm_with_tools`: send system prompt + schema context + conversation history + question to Gemini 2.5 Flash with the `execute_sql` tool declared; receive a tool call containing a SQL string.
   - `execute_query`: validate and run the SQL via DuckDB in-memory against the session's dataset files; record to `QueryLog` (timestamp, sql, dataset_name, row_count, latency_ms).
   - `format_response`: determine chart type from result shape (aggregation → bar/pie; time-series → line; else table-only); assemble `RichResponseModel`.
5. Runner yields SSE events: `status` (node transitions), `chunk` (markdown text tokens), `table` (JSON rows), `chart` (ChartSpec JSON), `done`.
6. Frontend `ChatThread` consumes the stream; `RichResponse` renders each event type as it arrives.
7. Completed message is persisted to `messages` table in SQLite.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini 2.5 Flash (`google-genai` SDK) | NL → SQL tool call generation | Graph transitions to `handle_error`; SSE `error` event sent to client; message saved with `status=failed` |
| DuckDB (in-process) | SQL execution against uploaded files | `execute_query` catches `duckdb.Error`; returns error message in SSE stream; query logged with `error` field |
| Filesystem (`data/uploads/`) | Dataset file storage | Upload endpoint returns 500 if directory write fails; startup validates/creates directory |

## Stack

> This project's concrete technology choices (captured at intake, filled by the spec-writer). The generic, every-project rules — model-naming, DB driver, dev port, test environment — live in `harness/patterns/tech-stack.md`; this section is only what **this** project picked.

- **Language:** Python 3.12+
- **Agent framework:** LangGraph (tool-use loop pattern: `call_llm_with_tools` → conditional edge → `execute_query` → `format_response`)
- **LLM provider + model:** Google Gemini via `google-genai` SDK; model `gemini-2.5-flash` (configurable via `AGENT_LLM_MODEL`)
- **Backend:** FastAPI 0.115+ with `StreamingResponse` (text/event-stream) for SSE
- **Database + ORM:** SQLite (single-user local tool) + SQLAlchemy 2.0 sync ORM + Alembic migrations
- **Analytical engine:** DuckDB in-process, in-memory per request; reads files via `read_csv_auto` / `read_json_auto` / openpyxl-exported temp parquet
- **Frontend:** Next.js 15.3 + React 19, static export (`output: 'export'`), mounted at `/app`
- **Styling:** Tailwind CSS v4 with `postcss.config.mjs` (`@tailwindcss/postcss` plugin — required for utility class generation)
- **Dependency management:** `uv` (Python) + `pyproject.toml`; `pnpm` (frontend)

| Key library | Version | Purpose |
|-------------|---------|---------|
| `langgraph` | ≥0.1 | Agent graph orchestration |
| `google-genai` | ≥2.9.0 | Gemini API client (already in pyproject.toml) |
| `duckdb` | ≥1.0 | In-process analytical SQL engine |
| `openpyxl` | ≥3.1 | Excel (.xlsx) file parsing for DuckDB ingestion |
| `python-multipart` | ≥0.0.9 | FastAPI `UploadFile` multipart form parsing |
| `sqlalchemy` | ≥2.0 | ORM for SQLite metadata tables |
| `alembic` | ≥1.13 | Database migrations |
| `chart.js` | ^4.x | Client-side chart rendering |
| `react-chartjs-2` | ^5.x | React wrapper for Chart.js |
| `structlog` | ≥24.1 | Structured logging (already in skeleton) |

**Avoid:**
- Dumping raw dataset rows into LLM prompts — schema-only context only (column names, types, row count).
- A persistent DuckDB database file — use in-memory connections per request to keep data lifecycles simple.
- Replacing SQLite with PostgreSQL — this is a single-user local tool; SQLite is the stated and appropriate choice.
- Third-party SSE libraries — use FastAPI `StreamingResponse` with `text/event-stream` directly.
- `pnpm dev` as the test/handoff path — the single-origin path is `pnpm build` + `uv run python -m src` + `http://localhost:8001/app/`.

## Deployment Model

Local single-user service. User runs `uv run python -m src` after building the frontend with `cd frontend && pnpm build`. FastAPI serves everything on `http://localhost:8001`. No containerization, cloud deployment, or reverse proxy is in scope.

> **Assumed:** DuckDB is used in-process (not as a persistent server). Each chat request opens a new DuckDB in-memory connection, registers the session's datasets as views, executes the query, and closes the connection.

> **Assumed:** Uploaded files are kept on the filesystem for the lifetime of the session. No TTL or automatic cleanup is implemented in Phase 1.

> **Assumed:** Multi-user isolation is session-based only (no authentication). Each session has a UUID stored in browser `localStorage`. All datasets are namespaced by `session_id` on disk.

> **Assumed:** Excel files are converted to a temporary Parquet or in-memory buffer via `openpyxl` before DuckDB reads them, since DuckDB's native Excel support requires the non-free `spatial` extension. The loader uses `openpyxl` → pandas DataFrame → `duckdb.register()` for Excel files.

> **Assumed:** `data/uploads/` is created at application startup if it does not exist (the `data/` directory already exists per the brief).
