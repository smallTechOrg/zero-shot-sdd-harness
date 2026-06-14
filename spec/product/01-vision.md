# Vision

## What This Agent Does

DataChat is a local web application that lets users upload CSV files and ask natural-language questions about their data. A user picks a CSV from their machine, uploads it, and then types questions like "What is the average sales amount by region?" or "Which product has the highest return rate?" — DataChat sends those questions along with the relevant column metadata and sample rows to the Google Gemini LLM and returns a plain-text answer. No SQL knowledge, no scripting, no pivot tables required.

## Who Uses It

Data-curious individuals — analysts, small business owners, students, or anyone who works with tabular data but does not want to write code or SQL. Their goal is to get quick, conversational answers from a CSV file without leaving the browser.

## Core Problem Being Solved

Opening a CSV in Excel or Google Sheets still requires the user to know what formula to write or what pivot to build. DataChat replaces that skill barrier with a plain English question, making the data instantly queryable for non-technical users.

## Success Criteria

- [ ] A user can upload a CSV file and receive a confirmation with the detected column names within 3 seconds
- [ ] A user can ask a natural-language question and receive a text answer derived from the CSV data within 10 seconds on a local machine
- [ ] The upload and query history persists across browser refreshes (stored in SQLite)
- [ ] The UI degrades gracefully when the Gemini API key is not configured, showing a stub-mode banner instead of crashing
- [ ] All endpoints return structured JSON errors (never raw 500 tracebacks) on bad input

## What This Agent Does NOT Do (Out of Scope)

- No charts, graphs, or data visualizations of any kind in v0.1
- No dashboard or saved-views feature
- No user authentication or multi-tenant access control
- No streaming of LLM responses (answers arrive in one shot)
- No CSV editing or data mutation
- No export of answers or reports
- No support for file formats other than CSV (Excel, Parquet, JSON, etc.)
- No cloud deployment — runs on localhost only in v0.1

## Key Constraints

- LLM provider: Google Gemini only via `google-generativeai` Python SDK; no OpenAI or Anthropic calls
- Backend: Python + FastAPI, single process, no task queue
- Database: SQLite via SQLAlchemy — no Postgres, no Redis
- UI: Plain HTML + vanilla JS served by FastAPI — no React, no build step
- Runs entirely on the developer's local machine
- No paid cloud services beyond the Gemini API key the user already holds
- CSV files are stored on disk in an `uploads/` directory relative to the project root

## Phases of Development

| Phase | Description | Success Gate |
|-------|-------------|--------------|
| 1 | Project scaffold — FastAPI app, SQLite schema, `uploads/` directory, stub HTML page served at `/` | Server starts, `GET /` returns 200, DB tables created on startup |
| 2 | CSV upload endpoint — `POST /api/uploads`, file saved to disk, metadata written to `uploads` table | Upload a 100-row CSV, verify row count and column names stored correctly |
| 3 | NL query endpoint — `POST /api/queries`, Gemini call with CSV context, answer returned and stored | Ask "how many rows?" against an uploaded CSV, receive a correct text answer |
| 4 | Web UI — upload panel + query panel wired to real endpoints, stub-mode banner | Full round-trip in browser: upload → question → answer displayed |
| 5 | Polish — error states, loading indicators, edge cases (empty CSV, malformed file, missing API key) | All error states display a user-friendly message; no raw tracebacks visible |
