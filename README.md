# Personal Data Analysis Agent

Upload a CSV file, ask questions in plain English, and get a factual answer plus an interactive chart — all running locally. No data leaves your machine (only a schema summary is sent to Gemini).

## What It Does

- Upload a CSV file via browser drag-and-drop or file browser
- Ask natural-language questions about your data (e.g., "What is the average revenue by region?")
- The agent plans the analysis, runs it with pandas, writes a plain-English answer, and renders a Plotly chart
- All CSV data stays on your local filesystem; only schema summaries and computed results are sent to the Gemini API

## Stack

- **Backend:** FastAPI + LangGraph + SQLite + pandas + Plotly
- **Frontend:** Next.js (static export, served by FastAPI at `/app`)
- **LLM:** Google Gemini (`gemini-2.5-flash`)

## Setup

### 1. Copy and fill `.env`

```bash
cp .env.example .env
```

Edit `.env` and set your Gemini API key:

```
AGENT_GEMINI_API_KEY=your-key-here
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Run DB migrations

```bash
uv run alembic upgrade head
uv run alembic current   # verify — must show: 0002 (head)
```

### 4. Build the frontend

```bash
cd frontend && pnpm install && pnpm build && cd ..
```

### 5. Start the server

```bash
uv run python -m src
```

Open `http://localhost:8001/app/` in your browser.

## Commands (all from repo root)

```bash
# Install dependencies
uv sync

# Run DB migrations
uv run alembic upgrade head
uv run alembic current           # verify current revision

# Build frontend
cd frontend && pnpm install && pnpm build && cd ..

# Start server
uv run python -m src

# Run all tests (requires AGENT_GEMINI_API_KEY in .env)
uv run pytest tests/ -v

# Run unit tests only (no API key needed)
uv run pytest tests/unit/ -v
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `AGENT_GEMINI_API_KEY` | Google Gemini API key (required) | — |
| `AGENT_DATABASE_URL` | SQLAlchemy database URL | `sqlite:///./data/agent.db` |
| `AGENT_LLM_MODEL` | Gemini model ID | `gemini-2.5-flash` |
| `PORT` | Server port | `8001` |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/datasets` | Upload a CSV file (multipart/form-data) |
| `GET` | `/datasets` | List all uploaded datasets |
| `POST` | `/analyses` | Run analysis: `{dataset_id, question}` |
| `GET` | `/analyses/{id}` | Retrieve a completed analysis |
| `GET` | `/health` | API health check |

## Project Layout

```
src/
  api/          — FastAPI routers (health, runs, datasets, analyses)
  config/       — Pydantic settings (AGENT_ prefix env vars)
  db/           — SQLAlchemy models (RunRow, DatasetRow, AnalysisRow) + session
  domain/       — Pydantic request/response models
  graph/        — LangGraph nodes, edges, state, runner
  llm/          — LLM client + providers (Gemini, Anthropic)
  prompts/      — System prompt templates (.md)
frontend/       — Next.js static export (served at /app)
tests/
  unit/         — Node logic, DB, API contract (no LLM key needed)
  integration/  — Full pipeline tests (requires real Gemini key)
alembic/        — DB migrations
spec/           — Agent spec: roadmap, architecture, capabilities, data, API, UI, agent graph
```

## How the Analysis Pipeline Works

```
CSV Upload → ingest_csv → plan_analysis (Gemini) → execute_analysis (pandas)
  → generate_answer (Gemini) → generate_chart (Plotly) → finalize → response
```

Any step failure routes to `handle_error`, which records the error in the DB and returns it in the API response — no crashes, no 5xx.
