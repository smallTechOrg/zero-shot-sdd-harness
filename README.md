# CSV Analyst — a local, privacy-first data-analysis agent

Upload a CSV in your browser, ask questions about it in plain English, get plain-English answers.
**Your raw data never leaves your machine** — all filtering, aggregation and math run locally in Python (pandas). Only your question plus a small *derived summary* (column names + types, summary statistics, small aggregates) is sent to a cheap cloud model (Gemini 2.5 Flash). The full dataset and individual rows are never transmitted.

> **All commands below run from the repo root** (the repo root *is* the project — there is no subdirectory to `cd` into). Every Python command is prefixed with `uv run`; bare `pytest`/`alembic`/`python` will fail unless you activate the venv manually.

---

## What it does (today — Phase 1)

- Open the web app, **upload a CSV**, and see its detected columns (name + type) and row count.
- **Ask a plain-English question** and get a plain-English answer computed from a **local** pandas profile — the numbers are grounded in your actual data. This includes group-by questions over any column (even high-cardinality keys like names/teams), derived ratios (e.g. *"which teams have the best average goals per match?"*), and totals/averages per category (e.g. *"which region has the highest total revenue?"*).
- A visible privacy note states the guarantee: only a summary and your question are sent to the AI.

**Labelled, not-yet-built (clearly marked in the UI so they're never mistaken for bugs):**
- **Charts & visual summaries** — *Coming in Phase 2*
- **Automatic patterns & anomalies** — *Coming in Phase 3*
- **Connect a database** — *Not planned (CSV files only)*

---

## Setup

```bash
cp .env.example .env
# edit .env: set your Gemini key
#   AGENT_GEMINI_API_KEY=<your key>
# the model is pinned to the cheap gemini-2.5-flash (AGENT_LLM_MODEL)
uv sync
```

Required `.env` values (documented in `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_GEMINI_API_KEY` | *(required)* | Gemini API key (the only secret) |
| `AGENT_LLM_MODEL` | `gemini-2.5-flash` | Cheap model, pinned for low cost |
| `AGENT_DATABASE_URL` | `sqlite:///./data/agent.db` | SQLite metadata + run history |
| `AGENT_MAX_UPLOAD_MB` | `25` | Max CSV upload size |

---

## Run

```bash
python agent.py --run        # applies migrations, builds the frontend, starts the server on :8001
```

Then open:

| URL | What |
|-----|------|
| `http://localhost:8001/app/` | **The app** — upload a CSV, ask a question, read the answer |
| `http://localhost:8001/health` | API health check |
| `http://localhost:8001/docs` | Interactive API docs (Swagger) |

To verify the database was migrated:

```bash
uv run alembic current        # must print a revision hash, not blank
```

---

## API (single origin, no auth — local tool)

Responses use the envelope `{"data": ..., "error": null}`.

- `POST /datasets` — multipart upload of a `.csv` `file`. Returns `{dataset_id, filename, row_count, schema:[{name, dtype, friendly_dtype}]}`. The raw CSV is written to `data/datasets/{id}.csv` (local disk); only metadata + schema are stored in SQLite.
- `POST /datasets/{dataset_id}/ask` — JSON `{question}`. Returns `{run_id, dataset_id, status, answer, error}`. The answer is computed from a local pandas profile; only the question + derived profile reach Gemini.

---

## Tests

The gate runs against the **real Gemini API** (key from `.env`) and SQLite:

```bash
uv run alembic upgrade head
AGENT_LLM_MODEL=gemini-2.5-flash uv run pytest tests/phase1 -q   # phase-1 gate (real Gemini)
uv run pytest tests/unit -q                                       # skeleton unit tests (no key needed)
```

The phase-1 suite includes the privacy-boundary proof: an automated test asserts the prompt sent to Gemini contains **no raw data row** — only the derived profile.

---

## How it stays private

```
LOCAL (your machine)                          CLOUD
─────────────────────────────────────         ──────────────
raw CSV on disk + full pandas DataFrame  ──►   (never sent)
        │
        ▼  derive locally
question + small profile (schema,        ──►   Gemini 2.5 Flash ──► plain-English answer
  summary stats, small aggregates)
```

The boundary is enforced in code at one place (`build_prompt`, in `src/graph/nodes.py`) and asserted by a test in every phase.

---

## Project layout

```
src/
  api/         ← FastAPI routers (health, datasets) + single-origin app factory
  config/      ← settings (AGENT_ prefix)
  datasets/    ← store.py (local CSV storage) + profiler.py (derived DataProfile)  ← privacy boundary
  db/          ← SQLAlchemy models (DatasetRow, RunRow) + session
  domain/      ← Pydantic request/response models
  graph/       ← LangGraph: load_profile → build_prompt → answer → finalize (+ error sink)
  llm/         ← LLM client + Gemini provider
  prompts/     ← answer.md (system prompt)
  observability/
frontend/      ← Next.js static export, served by FastAPI at /app
tests/
  phase1/      ← phase-1 gate (real Gemini + SQLite)
  unit/        ← unit tests (no key needed)
spec/          ← the spec (roadmap, architecture, agent, data, api, ui, capabilities)
agent.py       ← `python agent.py` to verify setup; `--run` to start the server
```

Built on the spec-first harness — see `spec/roadmap.md` for the full phased plan.
