# Data-Analysis Agent

> **All commands run from the repo root.** The repo root **is** the project — there is no backend subdirectory to `cd` into. Every backend command (`uv run ...`) runs from the repo root. The few frontend commands run from `frontend/`, and each block below states its working directory explicitly at the top.

A single-user, browser-based CSV/Excel data-analysis agent. You upload a file, ask questions in plain language, and watch the agent **plan → write pandas → run it server-side against the full dataset → inspect the result → refine** (bounded by a step limit). Each answer comes back as prose with the key numbers, an interactive chart, a results table, and the **exact code** it ran (shown collapsibly), and every run is saved to a per-dataset audit history.

The defining design constraint is a **hard privacy boundary**: only the file schema (column names, dtypes) and computed aggregates/results ever reach the LLM. **Raw data rows never leave the server** — the model writes code that executes locally and only ever sees the code's output.

## Stack

Python 3.12 + FastAPI (REST + SSE) + LangGraph + pandas, Google Gemini (`gemini-2.5-flash`), SQLite, Next.js 15 + Recharts. The frontend is static-exported and served by the backend at `/app`.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) — Python dependency + venv manager
- [`pnpm`](https://pnpm.io/) — frontend package manager
- A **Google Gemini API key**

## Setup

### 1. Configure environment

```bash
# working dir: repo root
cp .env.example .env
```

Then edit `.env` and set your Gemini key (note the **`AGENT_`** prefix on every variable):

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `AGENT_GEMINI_API_KEY` | **Yes** | _(empty)_ | Your Gemini API key |
| `AGENT_DATABASE_URL` | No | `sqlite:///./data/agent.db` | Local SQLite DB file |
| `AGENT_GEMINI_MODEL` | No | `gemini-2.5-flash` | Gemini model (cheap/fast tier) |
| `AGENT_MAX_STEPS` | No | `6` | Bounded plan→generate→execute→inspect→refine step limit |
| `AGENT_DATASET_STORE_DIR` | No | `data/datasets` | Where uploaded files are stored (never sent to the LLM) |
| `AGENT_COST_PER_1K_IN` | No | `0.00015` | Gemini input price per 1K tokens (USD) — keeps the cost meter accurate |
| `AGENT_COST_PER_1K_OUT` | No | `0.0006` | Gemini output price per 1K tokens (USD) |

### 2. Install Python dependencies

```bash
# working dir: repo root
uv sync
```

### 3. Run database migrations

```bash
# working dir: repo root
uv run alembic upgrade head
uv run alembic current
```

`uv run alembic current` **must print a revision hash** (not blank output) — blank means no migration was applied and the tables were not created.

### 4. Build the frontend

```bash
# working dir: frontend/
cd frontend
pnpm install
pnpm build
```

`pnpm build` produces a static export that the backend serves at `/app`.

## Run

```bash
# working dir: repo root
uv run python -m src
```

Then open **http://localhost:8001/app/**.

A sample CSV is provided at `data/samples/sales.csv`. Note that `data/` is **gitignored**, so on a fresh clone this sample may not be present — if it is missing, drag in any CSV of your own, or regenerate the sample locally.

## How to use it (the Phase 1 journey)

1. **Upload** a CSV — drag it in and watch the **auto-profile** panel populate (columns, dtypes, ranges, data-quality flags).
2. **Ask a question**, e.g. `What were total sales by region?`
3. **Watch the live reasoning** — the streamed `Step N of M` counter advances through plan → write code → run → inspect → refine.
4. **Read the answer** — prose with the key numbers, hover/zoom the **interactive chart**, scan the **results table**, and expand **"Show code"** to see the exact pandas it ran.
5. **Check the cost** — the per-question cost/token line and running daily total.
6. **Ask a follow-up**, e.g. `now break that down by month` — it understands the prior context.
7. **Open the history drawer** — every run for this dataset is listed for the audit trail.

**Labelled stubs (these are NOT bugs):**
- **Dataset Library** sidebar — greyed out, tagged "Coming in Phase 2".
- **Add another file / Join files** — greyed out, tagged "Coming in Phase 3".

## Tests

### Backend (real Gemini + real SQLite)

```bash
# working dir: repo root
uv run pytest tests/phase1 -q
```

Runs against the **real Gemini** API using the key in `.env` and the **real SQLite** database. Includes the privacy-boundary test (no raw row value ever appears in an outbound LLM payload) and the full-dataset test (code runs against the entire file, not a sample).

### Frontend E2E (Playwright)

```bash
# working dir: frontend/ (with the server running)
cd frontend
npx playwright test tests/e2e/
```

The backend (`uv run python -m src`) must be running first.

## API endpoints

REST + Server-Sent Events, port 8001. Full contract in `spec/api.md`.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/datasets` | Upload a CSV/Excel file; store, load, and auto-profile it |
| `POST` | `/datasets/{id}/ask` | Ask a question; **SSE** stream of live steps, then the final answer |
| `GET`  | `/datasets/{id}/runs` | Per-dataset audit history (list of past runs) |
| `GET`  | `/runs/{id}` | Full detail of one run — plan, steps, code, prose, chart, table, tokens, cost |
| `GET`  | `/usage/today` | Running daily cost/token total for the cost meter |

## Phase status

- **Phase 1 — done.** Single-file ask-and-answer with live reasoning, interactive chart + table + exact code, per-dataset history, and the enforced privacy boundary.
- **Phase 2 — planned.** Persistent dataset library across days (reopen a past dataset from a sidebar and continue asking).
- **Phase 3 — planned.** Multi-file joins / folder-as-one-dataset (the agent infers join keys and analyses across joined files).
</content>
