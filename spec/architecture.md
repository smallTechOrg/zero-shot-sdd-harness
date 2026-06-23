# Architecture

---

## System Overview

A single-process, local-first application. A FastAPI backend serves both a JSON API and a Next.js static-export UI from one origin (`http://localhost:8001/app/`). The user uploads a CSV; the backend ingests it into a real SQLite table and caches its schema. When the user asks a question, a LangGraph flow turns the question into a single read-only `SELECT` (via Gemini), validates it through a SQL sandbox, runs it locally against the dataset table, and asks the LLM to phrase a formatted answer over the small result set. Every operation is logged to an audit table. All metadata, conversation history, and audit entries live in the same local SQLite database, so dataset and history survive reloads. The only data that leaves the machine is the LLM prompt — which contains schema, a tiny row sample, and result sets, never full dataset rows.

## Component Map

```
[Browser: Next.js static export @ /app]
    │  same-origin fetch  /datasets /queries /audit
    ▼
[FastAPI app  (src/api)]
    │
    ├── datasets router ─► [CSV ingest  (src/ingest)] ─► creates ds_<id> table + schema cache
    │
    ├── queries router  ─► [Graph runner (src/graph/runner)]
    │                          │
    │                          ▼
    │                    [LangGraph flow (src/graph)]
    │                          │ schema+sample ──► [LLMClient → Gemini]  (text-to-SQL)
    │                          │ SQL ──► [SQL sandbox (src/sql)] ──► read-only execute
    │                          │ result set ──► [LLMClient → Gemini]  (answer)
    │                          └── writes audit entries every op
    │
    └── audit router    ─► reads audit_log

[SQLite  (data/agent.db)]  ── ORM tables: datasets, queries, audit_log
                           ── dynamic data tables: ds_<id>  (one per uploaded dataset)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| UI (Next.js static export) | Upload, ask, render answer text + table, audit panel, session restore; labelled stubs for deferred vision |
| API (FastAPI routers) | `datasets`, `queries`, `audit`; `ok`/`api_error` envelope; same-origin serving of `frontend/out` |
| Ingest (`src/ingest`) | Parse CSV, infer column types, create `ds_<id>` table, populate it, cache schema + sample |
| Agent (`src/graph`) | LangGraph text-to-SQL flow: generate SQL → validate/execute → compose answer; audit on each op |
| SQL sandbox (`src/sql`) | Validate generated SQL is a single read-only `SELECT`; execute read-only against the dataset table |
| Storage (`src/db`) | SQLAlchemy 2.0 ORM metadata/audit tables + Alembic migrations; dynamic `ds_<id>` data tables |

## Data Flow

**Ingest:**
1. Trigger: user uploads a CSV via `POST /datasets`.
2. Backend reads the CSV, infers column names + types, creates a `datasets` row to obtain an id.
3. Creates a real SQLite table `ds_<id>` and bulk-inserts the rows.
4. Computes and stores the cached schema (column names + types) and a ≤ 20-row sample on the `datasets` row.
5. Writes an `audit_log` entry (operation `ingest`, the `CREATE TABLE`/load summary, row count, columns, duration, success).
6. Output: the dataset metadata (id, name, table name, row count, columns) returned to the UI.

**Query:**
1. Trigger: user asks a question via `POST /queries`.
2. Graph runner creates a `queries` row (status `pending`) and invokes the LangGraph flow.
3. `generate_sql` node: prompt = system + cached schema + ≤ 20-row sample + the question → Gemini returns one `SELECT`. (No full rows in the prompt.)
4. `execute_sql` node: SQL sandbox validates it is a single read-only `SELECT` referencing only the dataset table, then executes it read-only; captures result rows + columns + row count + duration. Writes an `audit_log` entry (operation `query`, exact SQL, metadata, success/error).
5. `compose_answer` node: prompt = system + the question + the result set (already small; truncated to a cap if huge) → Gemini returns formatted text.
6. `finalize` node: persists the `queries` row (generated SQL, result columns/rows JSON, answer text, status `completed`).
7. Output: answer text + result table + audit metadata returned to the UI.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini (via `LLMClient`) | text-to-SQL generation and answer composition | Node sets `state["error"]`; query row marked `failed`; error surfaced in UI + audit |
| SQLite (`data/agent.db`) | dataset tables + metadata + audit + history | App cannot start / query fails; surfaced as `api_error` |

## Stack

> This project uses the existing repo skeleton **in place**. These are facts about the repo, honoured exactly.

- **Language:** Python 3.12+ (backend), TypeScript/React (frontend).
- **Agent framework:** LangGraph (the existing `src/graph/` flow, capability slot replaced in place).
- **LLM provider + model:** Google Gemini, default `gemini-2.5-flash`, via `LLMClient().call_model(prompt, *, system=None) -> str` (auto-detected from `AGENT_GEMINI_API_KEY`). Nodes call the LLM ONLY through `LLMClient` — never the SDK directly. Model is env-configurable via `AGENT_LLM_MODEL`.
- **Backend:** FastAPI. App factory in `src/api/__init__.py`; one router per resource; `ok(data)` / `api_error(code,msg,status)` envelope from `src/api/_common.py`.
- **Database + ORM:** SQLite (`AGENT_DATABASE_URL=sqlite:///./data/agent.db`) via SQLAlchemy 2.0 declarative + Alembic. ORM-managed metadata/audit tables coexist with dynamically-created `ds_<id>` data tables (raw SQL, read-only on the query path).
- **Frontend:** Next.js 15 static export (`output:'export'`, `basePath:'/app'`, `trailingSlash:true`), single entry `frontend/src/app/page.tsx`, Tailwind. Served by FastAPI from `frontend/out` at `/app`. Same-origin fetches.
- **Dependency management:** uv (`pyproject.toml`, `pythonpath=["src"]`, `packages=["src"]`, `testpaths=["tests"]`) for Python; pnpm for the frontend.

> **Assumed:** CSV parsing uses the Python standard library `csv` module plus simple type inference (int → float → datetime → text) rather than adding pandas — keeps the dependency surface minimal and ingest streamable. The generator may use pandas if it is already available, but no new heavy dependency should be added for Phase 1.

> **Assumed:** Type inference maps to SQLite affinities: `INTEGER`, `REAL`, `TEXT` (and `TEXT` for dates/booleans, stored as ISO strings / 0-1). Empty cells become SQL `NULL`.

| Key library | Version | Purpose |
|-------------|---------|---------|
| FastAPI | (skeleton-pinned) | HTTP API + static serving |
| LangGraph | (skeleton-pinned) | Agent flow |
| SQLAlchemy | 2.0 | ORM for metadata/audit tables |
| Alembic | (skeleton-pinned) | Migrations |
| google-genai | (already a dep) | Gemini provider behind `LLMClient` |
| Next.js / React | 15 / 19 | Static-export UI |
| Tailwind | v4 | Styling (requires `frontend/postcss.config.mjs`) |

**Avoid:** calling the Gemini SDK directly from nodes (use `LLMClient`); renaming the flat `src/` package to `src/agent/`; sending full dataset rows to the LLM; any non-`SELECT` SQL against dataset tables; PostgreSQL/other DB substitution (SQLite is the chosen, local store); a second server for the test path (single-origin `:8001/app/` only).

## Read-Only SQL Sandbox (`src/sql/sandbox.py`)

Generated SQL is untrusted model output and is enforced before execution:

- **Single statement, SELECT-only.** Reject anything that is not exactly one statement whose leading keyword is `SELECT` (or `WITH … SELECT`). Reject `;`-separated multiples.
- **Banned tokens.** Reject `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, `REPLACE`, `;` (beyond a single trailing one).
- **Table allow-list.** Only the `ds_<id>` table(s) for the active dataset(s) may be referenced — never the ORM metadata/audit tables.
- **Read-only execution.** Execute on a connection opened read-only (SQLite `mode=ro` / `query_only` PRAGMA set by the sandbox itself) with a row cap (default 5000) so a runaway query cannot exhaust memory.
- On any violation the sandbox raises; the node records the error in `audit_log` and sets `state["error"]`.

## Persistent Session Model

There is one implicit local session. State is the SQLite DB itself: `datasets` (uploaded files), `queries` (every question + answer + result), `audit_log`. The UI, on load, calls `GET /datasets` and `GET /queries` to rehydrate the most-recent dataset and the full query history, and `GET /audit` for the audit panel. No cookies or server-side session objects are required — reload = re-fetch.

## Deployment Model

Single local long-running process: `uv run python -m src` (uvicorn on port 8001) serving API + the built UI from one origin. SQLite file at `data/agent.db`. No external infra.
