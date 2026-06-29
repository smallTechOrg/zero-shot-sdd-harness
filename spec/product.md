# Product

## Vision

A conversational data analysis assistant that lets anyone — regardless of coding ability — explore tabular data (CSV files) by asking questions in plain English. The agent profiles uploaded data automatically, generates and executes Python/pandas code server-side, and returns answers as prose, tables, and interactive charts. Raw data never leaves the server.

## Target Users

- Personal daily analysts: individuals who work with CSV exports (sales reports, expense sheets, survey results) and want fast answers without writing SQL or Python
- Non-technical stakeholders: managers, marketers, product managers who receive data files and want self-service exploration
- Data-adjacent professionals: people with some data literacy who want to iterate quickly without coding

## Core Problem Solved

Non-technical users cannot query CSV data without writing code or uploading files to third-party services. This agent lets them ask questions in plain English, executes the code locally for privacy, and returns visual answers (charts, tables, prose) in one unified interface — no data ever sent to external services as raw rows.

## Success Criteria

- Upload a CSV and receive a complete profile card (row count, column types, null counts, sample values, quality flags) within 5 seconds
- Ask a natural-language question and receive a text answer plus an interactive Plotly chart within 15 seconds
- Conversation history preserved within a session: follow-up questions referencing prior context ("that column", "the same period") resolve correctly
- Raw data row values provably absent from every LLM prompt (verified by automated test)
- A non-technical user can use the app without any instructions

## Non-Goals

- **No persistence between sessions**: all data (uploaded files, conversation) is deleted when the session ends or the server restarts
- **No cloud storage**: files stay on the server's local disk in a temp directory for the session duration only
- **No real-time data**: only static file uploads (CSV, and Excel in Phase 2)
- **No SQL databases as input**: only CSV (Phase 1) and Excel (Phase 2)
- **No multi-user collaboration**: each session is isolated; no sharing between users
- **No authentication**: session IDs are unguessable UUIDs; no login required
- **No scheduled analysis**: no cron jobs or automated reports
- **No natural-language-to-SQL**: the agent generates pandas code, not SQL

## Key Constraints

- **Privacy**: raw CSV row values must never be sent to the LLM (Gemini). Only column names, dtypes, and statistical aggregates are sent.
- **Cost**: minimise LLM calls. Profile step uses zero LLM calls (pure pandas). Only Q&A turns call the LLM.
- **Local execution**: all pandas code runs server-side in a sandboxed exec() call, not in the browser or on an external service.
- **Session-only memory**: SQLite stores session metadata and conversation history for the duration of the session only.
- **Single server**: runs as a single FastAPI process on localhost:8001. Not designed for multi-process or cloud deployment.
