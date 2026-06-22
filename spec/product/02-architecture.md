# Architecture

> **Spec status:** Filled in for the **Senior Data Analyst Agent** (`data-analyst`), v0.1. Last updated 2026-06-22. Implementation details (libraries, versions) live in `spec/engineering/tech-stack.md`; this file describes the product-level shape.

---

## System Overview

A single user interacts with a local FastAPI web app: they create a session, upload datasets, and type natural-language questions. Each question is handled by a LangGraph agent that plans, generates SQL, executes that SQL against a local DuckDB analytical engine holding the user's datasets, and summarizes the result back into the chat. The agent keeps its own metadata (sessions, datasets registry, messages, audit log) in a **separate** SQLite metadata database. The defining architectural property is the **token-economy data flow**: the LLM only ever sees table schemas plus a small number of sample rows — the actual data is queried and aggregated entirely inside DuckDB, on the machine, and never sent to the model.

## Component Map

```
            ┌──────────────────────────────────────────────────┐
            │  FastAPI Web UI  (session view: datasets / chat / │
            │  audit panel)                                     │
            └───────────────┬──────────────────────────────────┘
                            │ HTTP (upload, ask, list)
                            ▼
            ┌──────────────────────────────────────────────────┐
            │  Application / service layer                      │
            │  - session & dataset services                     │
            │  - schema introspection + schema cache            │
            │  - audit writer                                   │
            └───────┬─────────────────────────────┬────────────┘
                    │ ask(question)               │ register / introspect
                    ▼                              ▼
   ┌────────────────────────────┐     ┌──────────────────────────────┐
   │  LangGraph agent           │     │  DuckDB analytical engine     │
   │  plan → generate_sql →     │◄───►│  (the USER DATASETS as tables)│
   │  execute_sql → summarize → │ SQL │  read-only analytical SQL     │
   │  finalize  (+ handle_error)│     └──────────────────────────────┘
   └───────┬────────────────────┘
           │ schema + sample rows only           ┌────────────────────┐
           ▼                                     │ SQLite metadata DB  │
   ┌────────────────────────────┐  read/write    │ (SQLAlchemy 2.0 +   │
   │  Google Gemini              │◄──────────────►│  Alembic)           │
   │  (Flash default; Pro        │   sessions /   │ Session, Dataset,   │
   │   escalation; stub fallback)│   datasets /   │ Message,            │
   └────────────────────────────┘   messages /    │ AuditLogEntry       │
                                     audit log     └────────────────────┘
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| Web UI (FastAPI + server-rendered templates) | Render session view; accept uploads and NL questions; display answers, result tables, and the audit panel |
| Service layer | Orchestrate session/dataset CRUD, register uploaded files into DuckDB, introspect & cache schemas, write audit entries, invoke the agent |
| Agent (LangGraph) | The plan → generate_sql → execute_sql → summarize → finalize loop, with a handle_error branch (see `07-agent-graph.md`) |
| Analytical store (DuckDB) | Holds the user datasets as tables; executes read-only analytical SQL and returns aggregated result sets |
| Metadata store (SQLite via SQLAlchemy 2.0 + Alembic) | Persists the agent's own state: sessions, dataset registry, conversation messages, audit log (see `04-data-model.md`) |
| LLM provider (Google Gemini, with stub fallback) | NL→SQL generation and result summarization, using schema + samples only |

**Dual-store rationale:** DuckDB is the analytical engine for user data; SQLite is the system-of-record for the agent's metadata. Keeping metadata in SQLAlchemy/Alembic preserves the boilerplate's migration gate machinery. User data (DuckDB) and agent metadata (SQLite) never mix.

## Data Flow

Two flows matter. Both keep raw data local.

**A. Dataset upload (registration)**
1. Trigger: user uploads a CSV/Parquet file in the session view.
2. The file is stored locally and ingested into DuckDB as a named table (table name derived from the dataset, scoped to the session).
3. The service introspects the table's schema (column names + types) and a small sample of rows; both are **cached** in the metadata DB alongside a `Dataset` record.
4. Output: the dataset appears in the session's dataset list, ready to query. No model call is made on upload.

**B. Natural-language question (the token-economy path)**
1. Trigger: user types a question into the chat; the request names the session.
2. The service assembles a **compact context**: for each dataset in the session, the cached schema + the few cached sample rows — and nothing else.
3. `plan` decides which datasets are relevant (using schemas only) and whether the question is routine or complex.
4. `generate_sql` sends *only* the relevant schemas + samples + the question to Gemini (`gemini-2.5-flash` by default; escalate to `gemini-2.5-pro` for complex reasoning) and gets back a single read-only SQL statement.
5. `execute_sql` runs that SQL in DuckDB. **Aggregation happens here, in the database** — full result rows are never round-tripped through the model.
6. `summarize` sends Gemini the question plus a **truncated** view of the (already-aggregated) result and gets a short natural-language answer; the full result table is rendered directly from DuckDB output, not from the model.
7. Throughout, each data operation is written to the audit log (NL prompt, generated SQL, row count, duration, timestamp).
8. Output: a chat message containing the text answer + a rendered result table; a new audit entry.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini API | NL→SQL generation and result summarization (`gemini-2.5-flash` default, `gemini-2.5-pro` escalation) | If no API key: auto-fallback to a clearly-signalled **stub** provider (UI banner). If a call errors mid-run: `handle_error` records the failure and returns a friendly error message; the app stays up. |
| DuckDB (embedded, local) | Stores user datasets; runs analytical SQL | Embedded library — no network. A failed/invalid query is caught by `execute_sql`, logged to the audit log with the error, and surfaced as an error message rather than crashing. |
| SQLite metadata DB (SQLAlchemy 2.0 + Alembic) | Persists sessions, datasets, messages, audit log | Embedded — no network. Migration applied via Alembic gate. Connection failure aborts the request with a 500; data is not lost (file-backed). |

## Deployment Model

Runs **locally** as a long-running FastAPI service (single process, single user). Both stores are local files: a DuckDB database file for user data and a SQLite file for metadata. No cloud, no multi-tenancy. The only outbound network call is to the Gemini API for schema-level NL→SQL/summarization — and that is skipped entirely in stub mode.
