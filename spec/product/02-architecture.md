# Architecture

## System Overview

The data analysis agent is a single-process FastAPI application. Users interact via a browser UI (Jinja2 templates). Uploaded CSVs are stored on disk; metadata, tools, capabilities, sessions, and query history live in SQLite. Each natural language query triggers a LangGraph ReAct pipeline that consults a **tool registry** to determine what actions are available, then iteratively calls those tools until the LLM signals a final answer.

The key architectural decision is that **tools are data, not code**. What the agent can do is stored in SQLite (`tools` + `tool_capabilities` tables), loaded at runtime, and dispatched through a generic executor. Adding a new data source type (API, GraphQL, shell) requires adding a new tool type and executor branch — not touching the agent loop or UI.

## Component Map

```
Browser (HTML form)
    ↓ POST /datasources/upload
FastAPI (uvicorn)
    │
    ├─► Tool Registry (SQLAlchemy)     ← loads DataSource + Tool + ToolCapabilities
    │
    └─► LangGraph Pipeline
            ├── load_data node         (load CSV into in-memory SQLite)
            ├── plan_action node       (LLM picks next tool capability + parameters)
            ├── execute_action node    (dispatch to tool executor by type)
            └── finalize node         (persist QueryRecord to SQLite)
                ↓
            SQLite (via SQLAlchemy 2.0)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| API (FastAPI) | HTTP routing, file upload, form handling, template rendering |
| Tool Registry | Load and validate DataSource → Tool → ToolCapability chains from DB |
| Graph (LangGraph) | Agent pipeline: load → plan → execute → loop → finalize |
| Tool Executors | Type-specific action execution (`csv_query` → in-memory SQLite) |
| LLM (OpenRouter) | Chat completions; falls back to stub when key not set |
| Domain | Pydantic/SQLAlchemy models for all entities |
| DB (SQLAlchemy + SQLite) | Persistence of all entities |
| Templates (Jinja2) | Server-rendered HTML: data sources, sessions, query history |

## Data Flow

1. **Upload:** User uploads a CSV → FastAPI saves the file, creates a `DataSource` record, creates a `Tool` (type `csv_query`) with a `ToolCapability` named `run_query`
2. **New session:** User starts a session on a DataSource → FastAPI creates a `Session` record → redirects to session page
3. **Query:** User asks a question in a session → FastAPI creates a `QueryRecord` and `AgentRun` → runs LangGraph
4. **Agent loop:**
   - `load_data`: reads CSV into in-memory SQLite, stores connection in `_db_cache[run_id]`
   - `plan_action`: sends schema + question + history to LLM → receives SQL (or `FINAL ANSWER:`)
   - `execute_action`: dispatches to tool executor (for `csv_query`: runs SQL, appends result to history)
   - loop back to `plan_action` until `FINAL ANSWER:` or max iterations
   - `finalize`: persists answer, token counts, SQL trace to DB; cleans up `_db_cache`
5. **Result:** FastAPI redirects to `GET /sessions/{id}?new={query_record_id}`; page highlights new answer inline

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| OpenRouter (Gemini 2.5 Flash) | NL reasoning and action planning | Falls back to stub — answer marked as "(stub mode)" |
| SQLite | Store all entities | App fails to start if DB file is unwritable |
| Local filesystem | Store uploaded CSV files | Upload fails with user-visible error |

## Deployment Model

Local single-user service. Runs with `uv run python -m data_analysis_agent` on port 8001. No container required for v0.1.
