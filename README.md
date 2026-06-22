# Senior Data Analyst Agent

> **All commands run from the repository root** (this directory — where `pyproject.toml` and `alembic.ini` live). There is no subdirectory to `cd` into.

Store multiple datasets, ask questions across them in **natural language**, and get back formatted text + result tables. Every SQL/data operation is written to an **audit log**. Sessions are **persistent** (survive restarts). Highly **token-economical**: only a dataset's schema and a few sample rows ever reach the LLM — never your raw data.

- **LLM:** Google Gemini (`gemini-2.5-flash` default, `gemini-2.5-pro` for complex questions). Runs in **offline stub mode** with no API key (the UI shows a banner) — set a key to enable real Gemini.
- **Engines:** [DuckDB](https://duckdb.org) runs analytical SQL over your datasets; a small SQLite store (SQLAlchemy + Alembic) holds sessions, the dataset registry, messages, and the audit log.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)

## Setup

```bash
# from the repo root
cp .env.example .env          # defaults work out of the box (stub mode)
uv sync                       # install dependencies
```

Create the metadata database schema (run from the repo root):

```bash
uv run alembic upgrade head
uv run alembic current        # must print a revision hash (e.g. "530216b527e1 (head)"), not blank
```

A blank `alembic current` means no migration was applied — re-run `upgrade head`.

## Run the app

```bash
# from the repo root
uv run python -m data_analyst
```

Then open **http://localhost:8001**.

1. Create a session.
2. Upload a CSV or Parquet file as a dataset.
3. Ask a question in natural language — the agent generates SQL, runs it in DuckDB, and shows the answer + table.
4. Check the **Audit log** panel to see every SQL/data operation.

### Enable real Gemini (optional)

Set your key in `.env` (no other flag needed — `provider=auto` switches automatically):

```bash
DATA_ANALYST_GEMINI_API_KEY=your-key-here
```

Without a key the app stays fully usable in **stub mode** (a banner makes this obvious).

## Run the tests

```bash
# from the repo root — no Gemini API key required
uv run pytest
```

Tests run against SQLite (the production metadata driver) and the real DuckDB engine, with the LLM stubbed — fully offline, no network.

## Configuration

All variables are prefixed `DATA_ANALYST_` (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATA_ANALYST_DATABASE_URL` | `sqlite:///./data/metadata.db` | SQLite metadata store |
| `DATA_ANALYST_DUCKDB_PATH` | `./data/datasets.duckdb` | DuckDB analytical engine file |
| `DATA_ANALYST_GEMINI_API_KEY` | _(empty)_ | Gemini key; empty = stub mode |
| `DATA_ANALYST_LLM_PROVIDER` | `auto` | `auto` \| `gemini` \| `stub` |
| `DATA_ANALYST_LLM_MODEL` | `gemini-2.5-flash` | NL→SQL / summary model |
| `DATA_ANALYST_LLM_MODEL_ESCALATION` | `gemini-2.5-pro` | Model for complex questions |
| `DATA_ANALYST_SAMPLE_ROWS` | `5` | Sample rows per dataset sent to the LLM |
| `DATA_ANALYST_PORT` | `8001` | Web server port |

## What's in v0.1

- Dataset management (upload CSV/Parquet, register, list)
- Natural-language cross-dataset queries → text + tables
- Audit logging of every SQL/data operation
- Persistent sessions

**Deferred to later phases:** charts, dashboards, deeper senior-analyst workflow simulation.

## Architecture

```
Browser (FastAPI + Jinja2, port 8001)
        │
        ▼
LangGraph agent:  plan → generate_sql → execute_sql → summarize → finalize   (+ handle_error)
        │                         │
   Gemini (schema + samples)      ▼
                            DuckDB (your datasets, analytical SQL — aggregation happens here)
        │
        ▼
SQLite metadata store: sessions · datasets · messages · audit log
```

Only schema + sample rows reach the LLM; raw data and full result sets never leave the machine.
