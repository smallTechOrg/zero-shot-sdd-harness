# Personal Data-Analysis Agent

Put your own spreadsheet in front of an AI analyst and ask questions in plain English. The agent auto-profiles your CSV/Excel, then for each question **writes real pandas, runs it locally against the full dataset, retries on error, and returns** a plain-language answer, key numbers, a short narrative, an interactive chart, a summary table, and the exact code it ran.

Only the dataset **schema, a few sample rows, and your question** ever leave the machine — the raw rows never go to the LLM.

> **All commands run from the repo root.**

---

## Prerequisites

- Python 3.11+ with [`uv`](https://docs.astral.sh/uv/)
- Node 18+ with [`pnpm`](https://pnpm.io/) (for the frontend build)
- A Google Gemini API key

## 1. Configure `.env`

Copy `.env.example` to `.env` and set your Gemini key:

```
AGENT_GEMINI_API_KEY=your-key-here
```

Optional tuning (defaults shown):

```
AGENT_EXEC_TIMEOUT_SECONDS=30   # wall-clock timeout for generated-code subprocess
AGENT_MAX_CODE_RETRIES=3        # bounded retries when generated code errors
```

The Gemini model defaults to `gemini-3.1-pro-preview`; override with `AGENT_LLM_MODEL` if needed.

## 2. Install & migrate

```bash
uv sync --extra dev
uv run alembic upgrade head
uv run alembic current      # should print the head revision
```

## 3. Build the frontend

```bash
cd frontend && pnpm install && pnpm build && cd ..
```

## 4. Run

```bash
uv run python -m src
```

Then open **http://localhost:8001/app/**.

---

## Using it

1. You land on a clean empty state: one upload box, plus greyed-out **"Coming soon"** stubs (Library, Projects, History, Cost meter, Multi-dataset selector).
2. Upload a CSV or Excel file. A **profile card** appears with the dataset name, exact row count, and each column's inferred type + quality flags (e.g. nulls).
3. Type a question (e.g. *"What were total sales by region?"*) and submit.
4. You get back a plain-language answer with the key numbers, a one-paragraph narrative, a rendered chart, a summary table, and a collapsible **"Show code"** panel with the exact pandas.

**Real vs stub (Phase 1):** upload, profile card, and question → answer + chart + table + code are all REAL end-to-end. The sidebar Library/Projects/History, the cost meter, live step-by-step progress, follow-up suggestions, and the multi-dataset selector are clearly-labelled Phase-2 stubs — not bugs.

---

## Tests

Tests run against **real Gemini** (key from `.env`) and the production SQLite driver — no stubs.

```bash
# Fast unit/contract tests (no LLM)
uv run pytest tests/unit -q

# End-to-end pipeline (real Gemini): upload the 50k fixture, ask a group-by
# question, assert the answer equals the independently-computed FULL-DATA value
uv run pytest tests/integration/test_phase1_pipeline.py -q
```

The 50,000-row fixture (`tests/fixtures/sales_50k.csv`, regenerate with
`uv run python tests/fixtures/make_sales_50k.py`) is engineered so a 5-row sample
sum is nowhere near the full-data sum — the test proving the agent computed on
**all** rows, not a preview.

### Phase-1 gate command

```bash
uv run alembic upgrade head && uv run pytest tests/integration/test_phase1_pipeline.py -q && (cd frontend && pnpm build) && uv run pytest tests/e2e/test_phase1_smoke.py -q
```

---

## API (Phase 1)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/datasets` | Upload a CSV/Excel file, profile it, return the profile card |
| `GET`  | `/datasets` | List uploaded datasets |
| `GET`  | `/datasets/{id}` | Fetch one dataset with its full profile |
| `POST` | `/runs` | Ask a plain-language question; runs the agent synchronously |
| `GET`  | `/runs/{id}` | Fetch a saved run |
| `GET`  | `/health` | Health check |

Every response uses the envelope `{"data": ..., "error": null}` on success, or an
HTTP error with `{"detail": {"code", "message"}}` on failure.

---

## How it works

The agent is a **LangGraph** pipeline: `load_context → generate_code → execute_code → write_answer → finalize`, with a bounded **retry** edge from `execute_code` back to `generate_code` when generated code errors. Generated pandas runs in a **timed subprocess** against the full local file; only the small aggregated result is returned. Structured logs (one context per `run_id`, one line per node) go to stdout.
