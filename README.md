# Data Analysis Agent

Upload a CSV file and ask questions about your data in plain English. Powered by Google Gemini + LangGraph, with a Model Context Protocol (MCP) tool layer: each uploaded file becomes an in-process MCP server that answers `run_query` calls with DuckDB over Parquet.

> **All commands run from the repo root.**

---

## Quick Start

### 1. Install dependencies

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set DATAANALYSIS_GEMINI_API_KEY to your Gemini API key
# Leave it blank to run in stub mode (offline, no real AI)
```

### 3. Apply database migrations

```bash
uv run alembic upgrade head
uv run alembic current   # must print a revision hash — blank means migration failed
```

### 4. Run the app

```bash
uv run python -m data_analysis_agent
```

Open [http://localhost:8001](http://localhost:8001) in your browser.

---

## Features (v0.1)

- **Datasets** — a *tool* is a named dataset (URI-addressed): an internal directory of Parquet files (one CSV → one table) or, in BETA, an external PostgreSQL database. Name it on upload, add more CSVs later, and the dataset's MCP server exposes one capability per table.
- **Natural Language Q&A** — type a question; the agent picks a dataset + table (`{"tool","capability","arguments"}`) and runs read-only DuckDB SQL (joins across a dataset's tables supported)
- **Sessions with memory** — each session keeps one MCP pool over its datasets and remembers prior Q&A (durable across restarts), so follow-up questions have context
- **Query History** — review past questions and answers per session

---

## Stub Mode

If `DATAANALYSIS_GEMINI_API_KEY` is not set, the app runs in **stub mode**:
- A yellow banner appears on every page
- Answers are placeholder text (not real AI output)
- No API calls are made — safe for offline development

---

## Running Tests

```bash
uv run pytest
```

All tests pass with no Gemini API key required (stub mode exercises the full MCP + DuckDB pipeline).

---

## Project Structure

```
src/data_analysis_agent/
├── api/          ← FastAPI routes
├── config/       ← Settings (pydantic-settings)
├── db/           ← SQLAlchemy models + session
├── domain/       ← Pydantic domain models
├── graph/        ← LangGraph pipeline (state, nodes, edges, runner); SqliteSaver memory
├── llm/          ← Gemini + stub provider
├── tools/        ← CSV→Parquet ingestion, table naming, LLM descriptions
│   ├── connectors/  ← dataset connectors: uri, base (protocol+factory), parquet, postgres (BETA)
│   └── mcp/         ← per-dataset MCP servers (server.py) + session pool manager (pool.py)
└── templates/    ← Jinja2 HTML templates

# datasets live under DATAANALYSIS_DATASETS_DIR/{dataset_id}/{table}.parquet

tests/
├── unit/         ← Pure unit tests (no DB, no network)
└── integration/  ← End-to-end pipeline + golden-path UI tests
```

---

## Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.12 |
| Web framework | FastAPI + uvicorn |
| UI | Jinja2 templates (React/Vite in Phase 4) |
| Agent | LangGraph (async nodes; one MCP pool + memory per session) |
| Tool protocol | Model Context Protocol — official `mcp` SDK 1.28.0 (one in-process FastMCP server per dataset, one tool per table) |
| Datasets | named, URI-addressed: internal `parquet:///{name}` (dir of Parquet files) or external `postgresql://…` (BETA, flag-gated) |
| Query engine | DuckDB (read-only; `read_parquet` for internal, `ATTACH … READ_ONLY` for Postgres) |
| Agent memory | LangGraph `SqliteSaver` checkpointer (durable, per session) |
| LLM | Google Gemini (`gemini-2.5-flash`) |
| Metadata DB | SQLite + SQLAlchemy 2.0 |
| Migrations | Alembic |

---

## Deferred (Future Phases)

- Charts and visualizations (Phase 4)
- AI-written insights / dataset summaries (Phase 5)
- React/Vite frontend (Phase 4)
- Multi-dataset management (Phase 6)
- User authentication (Phase 7)
