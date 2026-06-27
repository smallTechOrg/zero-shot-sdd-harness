# DataChat

> **All commands run from the repo root.** The repo root *is* the project — there is no subdirectory to `cd` into, except the one-time frontend build (`cd frontend && … && cd ..`). Every Python command is prefixed with `uv run`; a bare `alembic`/`pytest`/`python` will fail unless the venv is manually activated.

## What DataChat Is

DataChat is a local, single-user data-analysis chat agent. Upload a CSV or Excel (`.xlsx`) file, ask questions about it in plain language ("what were total sales by region?", then "break that down by month"), and get a plain-language answer plus an automatically-chosen inline chart (bar, line, or pie). The headline property is a **hard privacy boundary**: all computation over your data happens locally with pandas — only the dataset's *schema* (column names + types) and *locally-computed aggregate tables* are ever sent to Gemini. **Raw data rows never leave the machine.**

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) — Python dependency + venv manager (Python 3.11+).
- [`pnpm`](https://pnpm.io/) + Node.js — to build the frontend static export.
- A **Google Gemini API key** — the only secret you need to supply.

## Setup

All steps run from the repo root.

### 1. Configure your environment

Copy the example env file and fill in your Gemini key:

```bash
cp .env.example .env
```

Then edit `.env` and set:

```
AGENT_GEMINI_API_KEY=<your-gemini-api-key>
```

This is the only manual setup step. `PORT` defaults to `8001` (set it in `.env` only if you need a different port). The app's metadata database defaults to `sqlite:///./data/agent.db`.

### 2. Install Python dependencies

```bash
uv sync
```

This installs everything in `pyproject.toml` — pandas, openpyxl, langgraph, fastapi, sqlalchemy, alembic, and the rest.

### 3. Build the frontend

This is the only step that changes directory. It produces `frontend/out/`, which FastAPI serves at `/app`:

```bash
cd frontend && pnpm install && pnpm build && cd ..
```

### 4. Set up the database

Apply migrations against the production SQLite database, then verify they actually ran:

```bash
uv run alembic upgrade head
uv run alembic current
```

`uv run alembic current` **must print `0002 (head)`** — blank output means no migration was applied and the app will not work.

## Run

Start the server from the repo root:

```bash
uv run python -m src
```

It serves on `http://localhost:8001` (or `PORT` from `.env`). Then open:

```
http://localhost:8001/app/
```

> Use exactly `uv run python -m src`. It launches uvicorn with the flat `src/` package path set up. A bare `uvicorn api:app` fails because the package path is not configured.

## Using It

1. **Upload** — drag a CSV or `.xlsx` file (e.g. a sales export) onto the upload area. Within a few seconds you'll see the detected schema: column names, inferred types, and the row count.
2. **Ask** — type a plain-language question like *"what were total sales by region?"*. You'll get a plain-language answer grounded in a locally-computed aggregation, plus an auto-chosen **bar chart** rendered inline.
3. **Follow up** — ask *"show that as a trend over time"* or *"break it down by month"*. The agent uses the recent conversation context and returns a **line chart**.

When a question doesn't warrant a chart (e.g. a single-value answer), none is forced.

### Labelled "Coming soon" stubs (Phase 1)

These surfaces are visible but intentionally **non-functional** in Phase 1 — they are badged "Coming soon", not broken:

- **Connect a live database** (Phase 4)
- **Deep memory** indicator (Phase 2)
- **Auto-insights** panel (Phase 3)
- **Chart-type toggle** (manual chart override)

## API

The FastAPI service exposes four endpoints (full request/response shapes in [`spec/api.md`](spec/api.md)):

| Method & path | Purpose |
|---|---|
| `POST /datasets` | Multipart upload a CSV/`.xlsx` → dataset id + detected schema (no LLM call). |
| `POST /chat` | Ask a question about a dataset → plain-language answer + optional chart spec. |
| `GET /datasets/{dataset_id}` | Fetch a dataset's metadata + schema. |
| `GET /conversations/{conversation_id}` | Fetch a conversation's ordered message thread. |

All responses use the envelope `{"data": ..., "error": null}` on success.

## Testing

Run the full suite (the Phase-1 gate) from the repo root:

```bash
uv run alembic upgrade head && uv run pytest -q
```

The 32 local-logic tests (schema inference, aggregation, API contract, privacy-boundary construction) pass offline. The live-Gemini integration tests in `tests/integration/test_chat_graph.py` and `tests/integration/test_api.py` hit the **real Gemini API** and require a valid, **non-rate-limited** `AGENT_GEMINI_API_KEY` in `.env`; without an un-capped key they fail with a Gemini quota/billing error rather than a code defect.

## Privacy

The privacy boundary is the whole point of DataChat:

- Raw uploaded files live on local disk under `./data/uploads/` (gitignored) and are **never read into any LLM prompt**.
- Only the dataset **schema** and **locally-computed aggregate tables** (capped, small group-by results) are ever sent to Gemini.
- The aggregation arithmetic runs deterministically and locally with pandas. The LLM is used only to plan the aggregation and to phrase the answer + pick a chart from the small aggregate table.

## Stack

Python 3.11+ / FastAPI / LangGraph / SQLite / Gemini (`gemini-2.5-pro`) / Next.js + Recharts.
