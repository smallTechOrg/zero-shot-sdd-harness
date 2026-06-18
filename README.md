# DataChat

A data-analysis agent. Upload CSV files into a **dataset**, then ask questions about it in
**plain English** over a multi-turn chat. DataChat translates your question into a read-only SQL
query, runs it against your data, and answers with an explanation plus the result table.

It uses a **LangGraph ReAct loop** (inspect schema → write SQL → observe → answer) with **Google
Gemini**, a **DuckDB** analytical engine over your CSVs, and **SQLite** for app metadata. Every
generated query is validated **read-only** before it runs.

> **All commands run from the repo root.** The repo root *is* the project — there is no
> subdirectory to `cd` into.

## Requirements

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- A **Google Gemini API key** — DataChat is real-first; there is **no stub/offline mode**.
  Get one at https://aistudio.google.com/apikey

## Setup

Run from the repo root:

```bash
# 1. Install dependencies (creates .venv)
uv sync --extra dev

# 2. Configure environment
cp .env.example .env
# then edit .env and set DATA_ANALYST_GEMINI_API_KEY=<your key>

# 3. Create the database schema (SQLite)
uv run alembic upgrade head

# 4. Verify the migration was applied — must print a revision hash, not blank:
uv run alembic current
```

## Run the server

Run from the repo root:

```bash
uv run python -m datachat
```

The API serves on **http://localhost:8001** (set `PORT` to override).

## Run the chat UI (Next.js)

The web UI lives in [`frontend/`](frontend/) — a dataset picker + CSV upload, a multi-turn chat with a
live agent trace, rendered result tables, and **charts** (Recharts). It talks to the API above.

Run from the repo root (with the API server running):

```bash
cd frontend
npm install
npm run dev        # serves the UI on http://localhost:3000
```

Open **http://localhost:3000**. The UI calls the API at `http://localhost:8001` by default; override with
`NEXT_PUBLIC_API_BASE` (set it in `frontend/.env.local`). The API must allow the UI's origin — set
`DATA_ANALYST_CORS_ORIGINS` (defaults to `http://localhost:3000`).

## Try it (golden path)

Run from the repo root, with the server running:

```bash
# 1. Create a dataset
DS=$(curl -s -X POST localhost:8001/datasets \
  -H 'content-type: application/json' \
  -d '{"name":"Sales"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')

# 2. Upload a CSV
printf 'region,product,sales\nwest,widget,100\neast,widget,200\nwest,gadget,50\n' > /tmp/sales.csv
curl -s -X POST "localhost:8001/datasets/$DS/files" -F "files=@/tmp/sales.csv" >/dev/null

# 3. Start a conversation
CONV=$(curl -s -X POST localhost:8001/conversations \
  -H 'content-type: application/json' \
  -d "{\"dataset_id\":\"$DS\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')

# 4. Ask a question (streams the live agent trace + final answer over SSE)
curl -N -X POST "localhost:8001/conversations/$CONV/query" \
  -H 'content-type: application/json' \
  -d '{"question":"What is the total of all sales?"}'

# 5. Ask a follow-up (multi-turn — uses the prior turn as context)
curl -N -X POST "localhost:8001/conversations/$CONV/query" \
  -H 'content-type: application/json' \
  -d '{"question":"Now just the west region."}'
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/datasets` | Create a dataset (`{"name": "..."}`) |
| `GET` | `/datasets` | List datasets |
| `GET` | `/datasets/{id}` | Get a dataset + its files |
| `POST` | `/datasets/{id}/files` | Upload one or more CSV files (multipart `files`) |
| `DELETE` | `/datasets/{id}` | Delete a dataset (drops its DuckDB data) |
| `POST` | `/conversations` | Start a conversation (`{"dataset_id": "..."}`) |
| `POST` | `/conversations/{id}/query` | Ask a question — **SSE** stream of `step` → `answer` → `done` |
| `GET` | `/conversations/{id}` | Full conversation history |

Every JSON response uses the envelope `{"ok": true, "data": ...}` or
`{"ok": false, "error": {"code", "message"}}`.

## Tests

Run from the repo root. The LLM is **real** — set the key first.

```bash
# Unit + structure tests (no key needed; the real-Gemini tests skip without a key):
uv run pytest

# Full suite incl. the real ReAct loop, golden-path SSE, force_finalize, and evals:
DATA_ANALYST_GEMINI_API_KEY=<your key> uv run pytest
```

Tests use a file-backed `datachat_test.db` (override with `TEST_DATABASE_URL`), created and
dropped automatically. Assertions are loose (structure + key values) to absorb LLM output variance.

Run the eval suite directly:

```bash
DATA_ANALYST_GEMINI_API_KEY=<your key> uv run python -m evals.harness
```

### Frontend / end-to-end (Playwright)

The browser E2E drives the real stack (browser → Next.js → API → agent → DuckDB) and asserts the
post-JavaScript DOM (answer, result table, chart). It starts both servers itself; the backend needs the
Gemini key.

```bash
cd frontend
npm install
npx playwright install chromium      # once
DATA_ANALYST_GEMINI_API_KEY=<your key> CI=1 npm run test:e2e
```

## How it works

- **Agent loop** — a LangGraph `StateGraph` (`src/datachat/graph/`): `assemble_context` →
  `plan_action` (Gemini picks a tool) → `execute_action` → loop, ending when the model calls the
  `finish` tool. Bounded by `max_iterations` (default 6); on exhaustion it `force_finalize`s a
  best-effort answer rather than failing. Step events stream to the UI live as the agent works.
- **Tools (MCP)** — `inspect_schema`, `run_sql`, and `suggest_chart` are exposed as a real MCP server
  (`src/datachat/mcp/servers/sql_server.py`) and bound to Gemini in the graph; all delegate to the
  same read-only-safe implementations.
- **Charts** — when a chart helps, the agent calls `suggest_chart` (bar/line/pie) built from its last
  query result; the spec rides on the assistant message and the UI renders it with Recharts.
- **Action-safety** — model-generated SQL is parsed (sqlglot) and rejected unless it is a single
  read-only `SELECT`; the DuckDB query never mutates data.
- **Privacy** — only the schema + a small row sample (≤20 rows) is ever sent to the model; the full
  dataset stays in DuckDB.
- **Observability** — structured JSON logs bound to `run_id`, token/cost per run, OTel GenAI spans.

## Configuration (`.env`, `DATA_ANALYST_` prefix)

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATA_ANALYST_GEMINI_API_KEY` | — (**required**) | Google Gemini API key |
| `DATA_ANALYST_LLM_MODEL` | `gemini-2.5-flash` | Model name |
| `DATA_ANALYST_DATABASE_URL` | `sqlite+aiosqlite:///./datachat.db` | App metadata DB |
| `DATA_ANALYST_MAX_ITERATIONS` | `6` | ReAct loop ceiling |
| `DATA_ANALYST_MAX_UPLOAD_BYTES` | `52428800` | Per-file upload limit |
| `DATA_ANALYST_SAMPLE_ROWS` | `20` | Rows sampled for LLM grounding |
| `DATA_ANALYST_CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call the API (the UI) |
| `PORT` | `8001` | Server port |

Frontend: `NEXT_PUBLIC_API_BASE` (in `frontend/.env.local`, default `http://localhost:8001`).

## Scope

**Built:** CSV upload into a dataset, natural-language query (read-only SQL), multi-turn conversations
with text answers + result tables, a Next.js chat UI with a live agent trace, and **charts**
(bar/line/pie visualizations of a result).

**Deferred (Future Phases):** narrative insights, JSON & other file formats, cross-dataset joins,
long-term memory, retrieval/RAG. See `spec/product/01-vision.md` § Future Phases.

---

*Built spec-first from the [AI Agent Boilerplate](spec/). The spec in `spec/` is the source of truth.*
