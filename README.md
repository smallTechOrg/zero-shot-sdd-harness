# Data Analyst Agent

A conversational data analyst — upload CSV or JSON datasets, ask questions in natural language,
and get rich answers: markdown text, formatted tables, charts (bar/line/scatter/pie), and pinnable
dashboard panels. The agent behaves like a senior analyst: it generates read-only SQL, explains
its reasoning, and suggests follow-up questions.

**Stack:** FastAPI · LangGraph (ReAct agent loop) · DuckDB (per-dataset analytics) ·
SQLite (metadata, sessions, audit log) · Gemini 2.5 Flash · Next.js + Plotly (frontend)

## Prerequisites

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) (package/venv manager)
- Node.js ≥ 18 (frontend only)
- A Google Gemini API key — only needed for real LLM runs; all tests pass offline without one

## Quickstart

```bash
# 1. copy config and add your Gemini API key
cp .env.example .env
# edit .env and set: APP_LLM_API_KEY=your-key-here

# 2. install backend dependencies (runtime + dev/test)
uv sync --extra dev

# 3. run tests offline (no key, no network — FakeModel drives the agent loop)
uv run pytest

# 4. start the backend
uv run python -m src
# → http://localhost:8001  (/health, /traces, /docs)

# 5. start the frontend (separate terminal)
cd frontend && npm install && npm run dev
# → http://localhost:3000
```

## Key API routes

- `GET  /health` — liveness (200 offline, includes stub_mode flag)
- `POST /runs` — NL query; returns answer, SQL, chart_spec, follow_ups
- `POST /runs/stream` — same as SSE token stream
- `POST /upload` — ingest CSV/JSON (auto-creates dataset)
- `POST /datasets/{id}/files` — add file to existing dataset
- `GET  /datasets` — list all datasets with schema + row counts
- `DELETE /datasets/{id}` — remove dataset + DuckDB tables
- `GET  /sessions` — list past sessions with token usage
- `GET  /sessions/{id}` — session history with all query runs
- `GET  /audit-log` — last 100 SQL operations (filterable by session + date)
- `GET  /dashboard/{session_id}` — pinned panels for a session
- `POST /dashboard/{session_id}/panels` — pin a query result as a panel
- `DELETE /dashboard/{session_id}/panels/{panel_id}` — remove panel

## Configuration

All settings are `APP_`-prefixed environment variables (see `.env.example` and `src/config.py`).
Switching provider/model is a config change only — no code change needed.

## Layout

```
src/            backend package (config, db, domain, duck, graph, runner, server, tools, …)
tests/          offline unit + integration suite (FakeModel); tests/e2e/ excluded by default
frontend/       Next.js UI (upload, chat, charts, dashboard)
scripts/        demo_gate.sh — real-run gate
pyproject.toml  deps + pytest config
.env.example    APP_-prefixed config template (no secrets)
```
