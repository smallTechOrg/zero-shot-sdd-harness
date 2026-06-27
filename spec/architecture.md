# Architecture

## System Overview

The personal data analysis agent is a single-origin local web application. The user interacts through a Next.js browser UI served by a FastAPI backend running on `localhost:8001`. They upload a CSV file and type a natural-language question; a LangGraph agent graph ingests the file, calls Gemini to plan the analysis and write an answer, runs pandas to compute the result, generates a Plotly JSON chart spec, persists everything to a local SQLite database, and returns the answer and chart to the browser. No uploaded data ever leaves the local machine — only a schema summary (column names, dtypes, shape, and up to 5 sample rows) is sent to Gemini's API as part of the prompt.

## Component Map

```
Browser (Next.js static export @ /app)
    │  POST /datasets  (CSV upload)
    │  POST /analyses  (question + dataset_id)
    ▼
FastAPI (src/api/)
    │  uploads file → data/uploads/<dataset_id>.csv
    │  calls run_analysis(dataset_id, question) → run_id
    ▼
LangGraph Agent Graph (src/graph/)
    │
    ├─ ingest_csv      ── reads CSV from disk, computes schema summary + stats
    │                     writes DatasetRow to SQLite
    │
    ├─ plan_analysis   ── calls Gemini: schema summary + question → JSON plan
    │                     (what pandas ops to run; what chart type)
    │
    ├─ execute_analysis── runs pandas operations from plan → computed_data dict
    │
    ├─ generate_answer ── calls Gemini: computed_data + question → plain-English answer
    │
    ├─ generate_chart  ── builds Plotly figure dict from computed_data + plan → chart_json
    │
    ├─ finalize        ── persists AnalysisRow (answer, chart_json, status=completed)
    │
    └─ handle_error    ── persists AnalysisRow (status=failed, error_message)
    │
    ▼
SQLite DB (data/agent.db via SQLAlchemy + Alembic)
    datasets table
    analyses table
    runs table (existing — retained for backward compat)
    │
    ▼
FastAPI response → Browser renders answer text + Plotly chart
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| Presentation (`frontend/`) | Next.js static export; CSV upload, question form, answer display, Plotly chart render |
| API (`src/api/`) | FastAPI routes: file upload (`POST /datasets`), analysis trigger (`POST /analyses`), result fetch (`GET /analyses/{id}`) |
| Domain (`src/domain/`) | Pydantic request/response models for datasets and analyses |
| Agent graph (`src/graph/`) | LangGraph `StateGraph`; all analysis logic lives in nodes |
| LLM abstraction (`src/llm/`) | `LLMClient` + `GeminiProvider`; `call_model(prompt, system)` |
| Data (`src/db/`) | SQLAlchemy models, session factory, Alembic migrations |
| Config (`src/config/`) | `Settings` (pydantic-settings, `AGENT_` prefix, `extra="ignore"`) |

## Data Flow

1. **Trigger:** User selects a CSV file and clicks "Upload" — browser POSTs to `POST /datasets` (multipart/form-data).
2. **Upload:** FastAPI saves the file to `data/uploads/<dataset_id>.csv`, creates a `DatasetRow` (metadata only), returns `{ dataset_id, filename, row_count, column_names }`.
3. **Question:** User types a question and clicks "Analyze" — browser POSTs to `POST /analyses` with `{ dataset_id, question }`.
4. **Agent invocation:** The API route calls `run_analysis(dataset_id, question)` which invokes the LangGraph graph synchronously.
5. **Graph execution:** `ingest_csv` → `plan_analysis` (Gemini call) → `execute_analysis` (pandas) → `generate_answer` (Gemini call) → `generate_chart` (Plotly JSON) → `finalize` (writes `AnalysisRow`).
6. **Response:** API returns `{ analysis_id, answer_text, chart_json, status }` synchronously (blocking call; typical latency 5–15 s).
7. **Render:** Browser displays the plain-English answer and renders the Plotly chart via Plotly.js.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API (`generativelanguage.googleapis.com`) | LLM calls for planning and answer generation | `plan_analysis` and `generate_answer` nodes catch exceptions, set `state["error"]`, route to `handle_error`; user sees error message in browser |
| Local filesystem (`data/uploads/`) | Store uploaded CSV files | `ingest_csv` catches `FileNotFoundError`, sets `state["error"]` |
| SQLite (`data/agent.db`) | Persist datasets, analyses, runs | Fatal — FastAPI startup fails if DB is inaccessible; Alembic migration must succeed before first run |

## API Contract

All routes return `{ "data": <payload>, "error": null }` on success, or `{ "detail": { "code": "...", "message": "..." } }` on HTTP error. The analysis response is synchronous (no polling required for Phase 1).

### `POST /datasets`

Accepts `multipart/form-data` with a single `file` field (CSV).

**Response 200:**
```json
{
  "data": {
    "dataset_id": "uuid-string",
    "filename": "sales.csv",
    "row_count": 1200,
    "column_names": ["date", "revenue", "region"]
  },
  "error": null
}
```

**Error cases:**
- `413` — file exceeds 50 MB
- `400` — file is not parseable as CSV
- `500` — filesystem write failure

### `POST /analyses`

**Request:**
```json
{
  "dataset_id": "uuid-string",
  "question": "What is the average revenue by region?"
}
```

**Response 200:**
```json
{
  "data": {
    "analysis_id": "uuid-string",
    "dataset_id": "uuid-string",
    "question": "What is the average revenue by region?",
    "answer_text": "The average revenue is highest in the North region at $42,300...",
    "chart_json": "{\"data\": [...], \"layout\": {...}}",
    "status": "completed",
    "error": null
  },
  "error": null
}
```

If the agent fails, `status` is `"failed"`, `answer_text` is `null`, and `error` contains the error message. HTTP status is still `200` — the error is in the response body, never a 5xx (matching existing skeleton pattern).

**Error cases:**
- `400` — `dataset_id` not found
- `400` — `question` is empty

### `GET /datasets`

Returns all uploaded datasets (for the future dataset selector UI — stubbed in Phase 1 frontend).

**Response 200:**
```json
{
  "data": [
    { "dataset_id": "...", "filename": "...", "row_count": 1200, "uploaded_at": "2026-06-27T10:00:00Z" }
  ],
  "error": null
}
```

### `GET /analyses/{analysis_id}`

Returns a previously computed analysis by ID.

**Response 200:** Same shape as `POST /analyses` response `data` object.

## Data stays local

The Gemini API receives only:
1. The system prompt (from `src/prompts/analysis_plan.md` or `src/prompts/answer.md`)
2. The schema summary: column names, dtypes, data shape, and up to 5 sample rows (no raw CSV data)
3. The computed result dict from pandas (not the raw dataset)

The CSV file itself, and all computed data beyond what is in the prompt, stays on the local filesystem and SQLite database.

## Stack

> This project's concrete technology choices. Generic rules (model naming, DB driver, dev port, test environment) live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.11+ (existing skeleton constraint)
- **Agent framework:** LangGraph (already wired in `src/graph/`; `langgraph>=0.1` in `pyproject.toml`)
- **LLM provider + model:** Google Gemini via `google-genai` SDK — model `gemini-2.5-flash`, configurable via `AGENT_LLM_MODEL`. Provider auto-detected from `AGENT_GEMINI_API_KEY`.
- **Backend:** FastAPI (`fastapi>=0.115`, already in skeleton)
- **Database + ORM:** SQLite (`data/agent.db`) + SQLAlchemy 2.0 sync + Alembic migrations. SQLite is appropriate here: personal use, single-user, local-only tool.
- **Frontend:** Next.js 15 + React 19 + TypeScript, static export (`output: 'export'`, `basePath: '/app'`), served by FastAPI at `/app`
- **Dependency management:** uv (Python) + pyproject.toml; pnpm (frontend)

| Key library | Version | Purpose |
|-------------|---------|---------|
| `langgraph` | `>=0.1` | Agent graph (StateGraph, conditional edges) |
| `google-genai` | `>=2.9.0` | Gemini API client (already in pyproject.toml) |
| `pandas` | `>=2.2` | CSV parsing, data analysis operations |
| `plotly` | `>=5.22` | Server-side Plotly figure dict generation; serialized as JSON |
| `python-multipart` | `>=0.0.9` | FastAPI multipart file upload support |
| `fastapi` | `>=0.115` | HTTP API layer |
| `sqlalchemy` | `>=2.0` | ORM + session management |
| `alembic` | `>=1.13` | Database migrations |
| `pydantic-settings` | `>=2.3` | Settings with `AGENT_` prefix, `extra="ignore"` |
| `structlog` | `>=24.1` | Structured logging |
| `plotly.js-dist-min` | `>=2.35` | Frontend Plotly chart rendering (npm) |
| `next` | `15.3.0` | Frontend framework |
| `react` | `^19.0.0` | UI components |
| `tailwindcss` | `^4.1.8` | Styling |

**Avoid:**
- `asyncio`/`async def` in graph nodes — the existing skeleton uses sync SQLAlchemy and sync LangGraph invocation; keep nodes synchronous.
- `openpyxl` or other spreadsheet parsers in Phase 1 — CSV only; Excel support is out of scope.
- Sending raw CSV data to Gemini — only schema summaries and computed results go in prompts.
- `subprocess` or shell execution of user-supplied content — all analysis is done via pandas in-process.

## Deployment Model

Local development server only. The user runs:
```
cd frontend && pnpm build
uv run alembic upgrade head
uv run python -m src
```
Then opens `http://localhost:8001/app/` in a browser. No cloud deployment, no Docker, no CI/CD pipeline is required.
