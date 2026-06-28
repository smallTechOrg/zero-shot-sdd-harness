# Local Data Analyst

> **All commands run from the repo root.** The repo root IS the project — there is no subdirectory to `cd` into (except the one-time `cd frontend` for the static build, noted explicitly). Every Python command is prefixed with `uv run`; bare `alembic`/`pytest`/`python` will fail unless you have manually activated the venv.

A personal, **local-first** data-analysis agent. Upload a CSV, ask a question in plain language, and get back a correct written answer with the key numbers, a result table, and full transparency: the **plan** the agent made, the **code** it ran, and the **per-question cost** (tokens + estimated USD).

The defining property is the **privacy boundary**: your raw data never leaves the machine. The LLM only ever sees the column schema plus a few sample rows; the full dataset is analysed locally with DuckDB + pandas. Because the code runs over the *full* file, answers are exact — not silently sampled like a cloud chatbot.

---

## Phase 1 (current)

Upload one CSV → ask a plain-language question → get a correct answer + key numbers + result table, showing the plan, the code (collapsible), and the cost for that question. The LangGraph plan-then-execute agent with a step-cap cost guard is wired and real.

Everything else is a clearly-labelled non-functional stub (interactive charts, the persistent library & history, auto-profiling, follow-up suggestions, multi-file join, daily cost total) — coming in later phases.

## Stack

Python 3.12 · FastAPI · LangGraph (plan-then-execute graph) · Gemini `gemini-2.5-flash` (cheap Flash tier) · DuckDB + pandas (local analysis engine) · SQLite + SQLAlchemy + Alembic · Next.js static export served single-origin at `/app` (port 8001).

---

## Setup

```bash
# From the repo root:
cp .env.example .env
# Edit .env and set your Gemini key:
#   AGENT_GEMINI_API_KEY=<your key>
# (Flash model gemini-2.5-flash is the default; privacy/cost-guard settings are documented in .env.example.)

uv sync                                  # install Python deps
```

## Run

```bash
# From the repo root:
cd frontend && pnpm install && pnpm build   # build the static UI into frontend/out/
cd ..                                        # back to the repo root
uv run alembic upgrade head                  # create the SQLite tables
uv run alembic current                       # verify — must print a revision hash, not blank
uv run python -m src                         # start the server on port 8001
```

Then open:

| URL | What |
|-----|------|
| `http://localhost:8001/app/` | **The app** — upload a CSV, ask a question |
| `http://localhost:8001/health` | API health check |
| `http://localhost:8001/docs` | Interactive API docs (Swagger) |

Your uploaded files live locally in `data/uploads/` and the app state in `data/agent.db` (both gitignored — your data never leaves the machine).

## Test

```bash
# From the repo root — runs against the real Gemini Flash model using AGENT_GEMINI_API_KEY from .env:
uv run alembic upgrade head
uv run pytest

# Frontend end-to-end (requires the server running on :8001):
cd frontend && pnpm build && cd ..
uv run python -m src        # in one terminal
cd frontend && npx playwright test tests/e2e/ --reporter=line   # in another
```

---

## How it works (the privacy boundary)

1. **Upload** (`POST /datasets`) — the CSV is saved to `data/uploads/`; DuckDB extracts the column schema, a few sample rows, and the row/column counts. Raw rows are never stored in the database.
2. **Ask** (`POST /questions`) — the agent sends the LLM **only** the schema + sample rows + your question. The model drafts a plan and writes SQL/pandas code.
3. **Execute locally** — the generated code runs over the **full** dataset in DuckDB on your machine; only bounded aggregate results come back.
4. **Synthesize** — the LLM writes the plain-language answer + key numbers from those bounded results. A step cap (default 5) keeps cost low; if it's hit, you're warned rather than charged for runaway steps.
5. **Cost** — tokens in/out and an estimated USD are recorded and shown per question.

See `spec/architecture.md`, `spec/agent.md`, and `spec/roadmap.md` for the full design and phase plan.
