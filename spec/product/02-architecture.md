# Architecture

> **Boilerplate status:** Filled in by the tech-designer sub-agent after the product spec is approved.

---

## System Overview

The data-analyst agent is a web application that lets a user upload a CSV or JSON dataset and then ask natural-language questions about it through a chat interface. The backend is a FastAPI server hosting a LangGraph ReAct loop that uses Google Gemini to reason over the uploaded data via pandas. Each question triggers a new agent run: the LLM iteratively generates pandas operations, the executor runs them against the in-memory DataFrame, and results are streamed back to the UI as Server-Sent Events (SSE). Run metadata and chat history are persisted in SQLite. There is no dashboard or visualization layer in v0.1 — the product surface is upload + chat only.

## Component Map

```
Browser (React/Vite)
    │  HTTP REST (upload, list datasets)
    │  SSE stream (chat Q&A — step events + final answer)
    ▼
FastAPI Server  (:8001)
    │
    ├── POST /api/datasets/upload  → saves file to disk, creates DatasetRow
    ├── GET  /api/datasets         → lists uploaded datasets
    ├── POST /api/chat/ask         → creates RunRow, starts agent, streams SSE
    └── GET  /api/health           → liveness check
    │
    ▼
LangGraph Agent (ReAct loop)
    │
    ├── setup          → loads CSV/JSON into pandas DataFrame, stores in session store
    ├── plan_action    → calls Gemini; outputs next pandas operation or FINAL ANSWER
    ├── execute_action → validates action against allowlist; runs via getattr(df, method)
    ├── finalize       → persists answer + usage to DB; emits final SSE event
    ├── force_finalize → synthesises best-effort answer from action_history (max iterations hit)
    └── handle_error   → persists failure to DB; emits error SSE event
    │
    ├──► Google Gemini API  (gemini-2.5-flash — LLM calls from plan_action)
    ├──► pandas             (DataFrame operations in execute_action)
    └──► SQLite             (run metadata, dataset registry, chat history)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| **Browser UI** | File upload form, dataset picker, chat input/output, SSE-driven step trace display |
| **API (FastAPI)** | Request validation, file storage, run lifecycle management, SSE streaming |
| **Agent graph (LangGraph)** | ReAct loop orchestration — routes between nodes based on LLM output and iteration count |
| **LLM client** | Wraps `google-generativeai`; handles prompt formatting, response parsing, token accounting |
| **Pandas executor** | Allowlist validation + safe execution of LLM-generated operations against DataFrame |
| **Storage (SQLite)** | Persistent run metadata, uploaded dataset registry, chat message history |
| **Module-level DataFrame store** | In-memory dict keyed by `session_id` holding loaded DataFrames across loop iterations |

## Data Flow

1. **Trigger:** User selects an uploaded dataset and submits a natural-language question via the chat UI. The browser sends `POST /api/chat/ask` with `{ session_id, dataset_id, question }`.

2. **Setup:** FastAPI creates a `RunRow` in SQLite (status=`running`), then invokes the LangGraph agent. The `setup` node reads the dataset file path from the DB, loads it into a pandas DataFrame using `pd.read_csv` or `pd.read_json`, and stores it in the module-level `_dataframe_store` dict keyed by `session_id`.

3. **Plan (reason):** The `plan_action` node builds a prompt containing the dataset schema (column names + dtypes + first 3 rows), the user question, and the full `action_history` so far. It calls Gemini and receives either a pandas operation string (e.g. `groupby('category').agg({'sales': 'sum'})`) or a line starting with `FINAL ANSWER:`.

4. **Route:** The edge function `after_plan_action` checks the raw LLM response:
   - `FINAL ANSWER:` prefix → route to `finalize`
   - `iteration_count >= max_agent_iterations` → route to `force_finalize`
   - Otherwise → route to `execute_action`

5. **Act (execute):** The `execute_action` node passes the action string to `tools/pandas_executor.py`. The executor validates the operation against the allowlist, calls it via `getattr(df, method)(*args)`, and serialises the result (first 20 rows as JSON if a DataFrame, else the scalar value). On error, it returns an error string. The result is appended to `action_history` with `is_error` flag and the iteration count is incremented. An SSE event is emitted with the step result so the UI can display it in real time.

6. **Observe (loop back):** After `execute_action`, the edge routes back to `plan_action`. The LLM now sees the action and its result in `action_history` and can plan the next step — this is the observe phase of ReAct.

7. **Finalize / force-finalize:** On `FINAL ANSWER:`, `finalize` strips the prefix, persists the answer and usage stats to the `RunRow`, releases the DataFrame from the store, and emits a final SSE event. On iteration exhaustion, `force_finalize` makes one more LLM call asking it to synthesise the best answer from `action_history` with a note that iterations were exhausted.

8. **Output:** The browser receives a stream of SSE events — one per `execute_action` result (step trace), then a final event with the answer text. The UI renders each step in a collapsible trace panel and displays the final answer in the chat thread.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini API (`gemini-2.5-flash`) | LLM reasoning for plan_action and force_finalize | Fatal — if LLM is down, the run fails with `handle_error`; error is persisted and streamed to UI |
| SQLite (file on disk) | Run metadata, dataset registry, chat history | Fatal — if DB file is inaccessible at startup, server refuses to start (fail loudly) |
| Local filesystem (uploaded files) | Storing uploaded CSV/JSON between upload and agent run | Fatal — if dataset file is missing when `setup` runs, the run fails with `handle_error` |
| pandas (in-process) | DataFrame loading and operation execution | Recoverable — pandas exceptions in `execute_action` append an error to history and loop back |
| pnpm / Vite build (frontend) | Static asset build for production | Build-time only — does not affect runtime |

## Deployment Model

**Local development (v0.1):** Single-machine, single-process. The FastAPI server runs with `uv run uvicorn data_analyst.api:app --port 8001 --reload`. The Vite dev server runs separately on port 5173 with a proxy for `/api/*` to 8001. SQLite database file lives at the path specified by `DATA_ANALYST_DATABASE_URL` (default: `sqlite:///./data_analyst.db` in the repo root). Uploaded files are stored in a configurable directory (default: `./uploads/`).

**Production (future):** The Vite build output (`dist/`) is served as static files by FastAPI via `StaticFiles`. A single `uvicorn` process serves both the API and the UI. SQLite remains the database unless traffic requires PostgreSQL.

There is no containerisation, cloud deployment, or background worker queue in v0.1. The agent runs synchronously inside the FastAPI request/response cycle, with the SSE stream keeping the connection alive for the duration of the run.

## Session and State Management

- Each upload creates a `DatasetRow` with a stable `dataset_id`.
- Each question-answer exchange creates a `RunRow` with a `session_id` (browser tab identifier, a UUID generated client-side and sent with every request).
- The in-memory `_dataframe_store: dict[str, pd.DataFrame]` is keyed by `session_id`. The DataFrame is loaded once in `setup` and released in every terminal node (`finalize`, `force_finalize`, `handle_error`) to prevent memory leaks.
- Multiple concurrent sessions each have their own keyed slot — there is no shared mutable DataFrame state between sessions.
- The `RunRow` persists `action_history` as JSON text, enabling replay and audit even after the in-memory state is released.
