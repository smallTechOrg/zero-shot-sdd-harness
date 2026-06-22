# Data Model

> **Spec status:** Filled in for the **Senior Data Analyst Agent** (`data-analyst`), v0.1. Last updated 2026-06-22.

---

## Storage Technology

**Dual store.** Two stores with strictly separate roles (see `02-architecture.md`):

- **DuckDB (analytical store)** — holds the **user datasets themselves** as tables and executes read-only analytical SQL. There is one DuckDB table per registered dataset, named deterministically and scoped to its session. DuckDB is *not* described entity-by-entity here because its tables are user-defined (their columns come from the uploaded files); the metadata DB records *that* they exist and their cached schema.
- **SQLite metadata DB (system-of-record), via SQLAlchemy 2.0 + Alembic** — holds the agent's own metadata: `Session`, `Dataset`, `Message`, `AuditLogEntry`. Using SQLAlchemy + Alembic keeps the boilerplate's migration gate intact.

Rationale for splitting: user data and agent metadata have different lifecycles, different query engines, and a hard rule that raw user data never mixes with metadata or leaves the machine.

## Entities

All four entities below live in the **SQLite metadata DB**.

### Entity: Session

A persistent workspace that groups a set of datasets and a conversation. Survives process restarts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key |
| name | string | yes | Human label, e.g. "Q2 billing review" |
| created_at | datetime (UTC) | yes | When the session was created |
| updated_at | datetime (UTC) | yes | Last activity (upload or question) |

### Entity: Dataset

A registered user file: one row per uploaded CSV/Parquet, paired with one DuckDB table. Stores the **cached** schema and sample rows that feed the LLM.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key |
| session_id | int (FK → Session.id) | yes | Owning session |
| name | string | yes | Display name (default: filename stem), e.g. "invoices" |
| source_filename | string | yes | Original uploaded filename, e.g. "invoices_2026q2.csv" |
| file_format | enum(`csv`,`parquet`) | yes | Source format |
| duckdb_table | string | yes | Deterministic, session-scoped table name in DuckDB, e.g. "s12_invoices" |
| row_count | int | yes | Number of rows ingested, e.g. 4821 |
| schema_json | JSON | yes | Cached column names + types, e.g. `[{"name":"amount","type":"DECIMAL"}]` |
| sample_rows_json | JSON | yes | ≤ N cached sample rows (token-economy source), N small/configurable |
| created_at | datetime (UTC) | yes | Registration time |

### Entity: Message

One turn of conversation in a session. Persists history so it survives restarts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key |
| session_id | int (FK → Session.id) | yes | Owning session |
| role | enum(`user`,`assistant`) | yes | Who produced the message |
| content | text | yes | The NL question (user) or the NL answer (assistant) |
| generated_sql | text | no | SQL produced for an assistant message (null for user turns / non-SQL replies) |
| result_table_json | JSON | no | Rendered result table (columns + rows) for an assistant answer, from DuckDB output |
| created_at | datetime (UTC) | yes | When the message was created |

### Entity: AuditLogEntry

An append-only record of one SQL/data operation. See capability `03-audit-logging.md`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | int (PK) | yes | Primary key |
| session_id | int (FK → Session.id) | yes | Owning session |
| nl_prompt | text | no | NL question that triggered the op (null for some non-NL ops, e.g. ingest) |
| generated_sql | text | no | The SQL that ran (null if it failed before SQL was produced) |
| row_count | int | no | Rows returned (null on failure) |
| duration_ms | int | yes | Wall-clock duration of the data op |
| status | enum(`success`,`error`) | yes | Outcome |
| error_message | text | no | Present when status=error |
| created_at | datetime (UTC) | yes | Timestamp of the operation |

### Relationships

- `Session` 1 — N `Dataset`
- `Session` 1 — N `Message`
- `Session` 1 — N `AuditLogEntry`
- Each `Dataset` ↔ exactly one DuckDB table (referenced by `Dataset.duckdb_table`).

```
Session ──< Dataset ──(1:1)── DuckDB table (user data)
   │
   ├──< Message
   └──< AuditLogEntry
```

## Data Lifecycle

- **Session** created on demand; `updated_at` bumped on each upload or question. Persists indefinitely in v0.1 (no archival).
- **Dataset** created on upload: file ingested into DuckDB, schema + samples cached. Lives for the life of the session. (No edit/re-upload flow in v0.1.)
- **Message** appended per conversation turn; never edited or deleted in v0.1.
- **AuditLogEntry** appended per data op; **append-only**, never edited or deleted in v0.1.
- Nothing is time-boxed or auto-archived in v0.1.

## Sensitive Data

- **User datasets may contain PII/business-sensitive data.** They are stored and queried **locally only** (DuckDB + local files) and **never sent to the LLM or off the machine** — only cached schema + ≤ N sample rows reach the model. Note: sample rows *can* contain real values, so N is kept small; treat sample rows as the only data that leaves for the model.
- The **Gemini API key** (env `DATA_ANALYST_GEMINI_API_KEY`) is a secret: read from the environment, never committed, never written to the metadata DB or the audit log.
- `generated_sql` and `result_table_json` may embed data-derived values; they live only in the local metadata DB.
