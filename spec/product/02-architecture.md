# Architecture

## System Overview

DataChat is a single-process Python application. A FastAPI server handles all HTTP traffic — serving the static HTML/JS frontend, accepting file uploads, and proxying natural-language queries to the Google Gemini API. Uploaded CSV files are stored on disk under `uploads/`. All metadata (upload records, query history) is persisted in a local SQLite database managed by SQLAlchemy. There are no background workers, no message queues, and no external services beyond the Gemini API.

## Component Map

```
Browser (HTML + vanilla JS)
        |
        | HTTP (REST + multipart)
        ↓
FastAPI Application  ──────────────────────────────────────────┐
  ├── Static file handler (serves index.html + assets)         │
  ├── Upload router   (/api/uploads)                           │
  │     └── CSV Parser (pandas)                                │
  │           └── Disk storage  (uploads/ directory)           │
  └── Query router    (/api/queries)                            │
        └── Gemini Client (google-generativeai SDK)  ──────────┼──→  Google Gemini API
                                                               │
SQLite Database (SQLAlchemy ORM)  ←────────────────────────────┘
  ├── uploads table
  └── queries table
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| Presentation | Plain HTML + vanilla JS; no build step; served by FastAPI's `StaticFiles` or an inline route |
| API | FastAPI routers — validates request input with Pydantic models, delegates to service layer |
| Service | Business logic: CSV parsing, prompt construction, Gemini call, result storage |
| Storage | SQLAlchemy ORM models; SQLite file at `data/datachat.db`; raw CSV files in `uploads/` |
| LLM Client | Thin wrapper around `google-generativeai`; accepts prompt string, returns answer string |

## Data Flow

### Upload flow

1. Trigger: User selects a CSV file in the browser and clicks "Upload"
2. Browser sends `POST /api/uploads` with `multipart/form-data`
3. FastAPI saves the raw file to `uploads/<uuid>.csv` on disk
4. Service layer reads the file with pandas: extracts row count and column names
5. A record is inserted into the `uploads` table in SQLite
6. Response: JSON with `upload_id`, `filename`, `row_count`, `columns`

### Query flow

1. Trigger: User types a question and clicks "Ask"
2. Browser sends `POST /api/queries` with `{ "upload_id": "...", "question": "..." }`
3. FastAPI loads the matching upload record from SQLite
4. Service reads the CSV from disk, takes the first 20 rows as sample data
5. Constructs a Gemini prompt: column names + sample rows (CSV text) + user question
6. Calls Gemini API; receives text answer
7. Inserts a record into the `queries` table (question + answer)
8. Response: JSON with `query_id`, `answer`

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini API (`gemini-1.5-flash` or similar) | Generates natural-language answers from CSV context prompts | If key is missing or quota exceeded, return a 503 with a user-friendly message; UI shows stub-mode banner when key is absent |
| `google-generativeai` Python SDK | Official client for Gemini API | Version pinned in `requirements.txt`; failure surfaces as a 500 |
| `pandas` | CSV parsing, row count, column extraction, sample row generation | Malformed CSVs caught and returned as 422 with a descriptive error |
| `SQLAlchemy` + `aiosqlite` (or `sqlite3`) | ORM and SQLite driver | Database file created on startup if absent; errors surface as 500 |

## Deployment Model

Single-process local server. The developer runs:

```
uvicorn src.main:app --reload --port 8000
```

The app is accessed at `http://localhost:8000`. The `uploads/` directory and `data/` directory are created automatically on first run if they do not exist. There is no Docker requirement for v0.1, though a `Dockerfile` may be added in a later phase.
