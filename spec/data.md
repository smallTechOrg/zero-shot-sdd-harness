# Data Model

---

## Storage Technology

SQLite (`AGENT_DATABASE_URL=sqlite:///./data/agent.db`), accessed via SQLAlchemy 2.0 declarative ORM for the metadata/audit tables and via raw (read-only) SQL for the dynamic per-dataset data tables. Alembic manages the ORM-table schema. Local-only; the file IS the persistent session.

Two kinds of tables coexist in the one database:
1. **ORM-managed metadata/audit tables** — `datasets`, `queries`, `audit_log` (defined in `src/db/models.py`, migrated by Alembic).
2. **Dynamic per-dataset data tables** — `ds_<dataset_id_safe>`, one created per uploaded CSV at ingest, holding the actual rows. These are NOT ORM models and NOT in Alembic; they are created/dropped at runtime by the ingest code. Generated query SQL runs read-only against these only.

> **Assumed:** The `datasets` primary key is a UUID string (matching the skeleton's `RunRow.id` convention). The dynamic table name is `ds_` + the UUID with hyphens replaced by underscores, e.g. `ds_3f2a..._...`, to be a valid SQL identifier.

---

## Entities

### Entity: Dataset (`datasets`)

A single uploaded CSV, its backing data table, and the cached schema/sample used to keep LLM prompts tiny.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | Text (UUID) | yes | Primary key |
| `name` | Text | yes | Display name (defaults to the uploaded filename) |
| `table_name` | Text | yes | Name of the backing data table, e.g. `ds_<id_safe>` |
| `row_count` | Integer | yes | Number of rows loaded |
| `columns_json` | Text (JSON) | yes | Ordered list of `{name, type}` (the cached schema) |
| `schema_text` | Text | yes | Pre-rendered schema string for the LLM prompt |
| `sample_text` | Text | yes | Pre-rendered ≤ 20-row sample string for the LLM prompt |
| `created_at` | TIMESTAMP(tz) | yes | Ingest time |

### Entity: Query (`queries`)

One natural-language question and its result — the persistent conversation/history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | Text (UUID) | yes | Primary key |
| `dataset_id` | Text (FK → datasets.id) | yes | The dataset queried |
| `question` | Text | yes | The user's NL question |
| `generated_sql` | Text | no | The SQL the LLM produced (null if generation failed) |
| `answer_text` | Text | no | The formatted answer (null on failure) |
| `result_columns_json` | Text (JSON) | no | Result column names |
| `result_rows_json` | Text (JSON) | no | Result rows (capped) |
| `row_count` | Integer | no | Result row count |
| `status` | Text | yes | `pending` \| `completed` \| `failed` |
| `error_message` | Text | no | Set when `status=failed` |
| `created_at` | TIMESTAMP(tz) | yes | Ask time |

### Entity: AuditLogEntry (`audit_log`)

First-class record of EVERY data operation (ingest and query). Read API + UI panel.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | Text (UUID) | yes | Primary key |
| `operation` | Text | yes | `ingest` \| `query` |
| `dataset_id` | Text (FK → datasets.id) | no | Related dataset (null only if ingest failed pre-row) |
| `query_id` | Text (FK → queries.id) | no | Related query (null for ingest) |
| `sql_text` | Text | no | The exact SQL executed (the SELECT, or ingest load summary) |
| `row_count` | Integer | no | Rows affected/returned |
| `columns_json` | Text (JSON) | no | Column names involved |
| `duration_ms` | Integer | yes | Operation duration |
| `success` | Boolean | yes | Whether the op succeeded |
| `error_message` | Text | no | Set when `success=false` |
| `created_at` | TIMESTAMP(tz) | yes | Operation timestamp |

### Dynamic data tables (`ds_<id_safe>`)

Created at ingest, one per dataset. Columns mirror the CSV headers with inferred SQLite affinities (`INTEGER` / `REAL` / `TEXT`). Empty cells → `NULL`. Not ORM-modelled; queried read-only only.

---

## Relationships

```
datasets (1) ──< (N) queries          (queries.dataset_id → datasets.id)
datasets (1) ──< (N) audit_log         (audit_log.dataset_id → datasets.id)
queries  (1) ──< (N) audit_log         (audit_log.query_id → queries.id)
datasets (1) ──  (1) ds_<id_safe>      (datasets.table_name names the data table)
```

## Lifecycle

- **Ingest:** create `datasets` row → create `ds_<id_safe>` table + load rows → fill cached `columns_json`/`schema_text`/`sample_text`/`row_count` → write `audit_log` (op `ingest`).
- **Query:** create `queries` row (`pending`) → run graph → write `audit_log` (op `query`, success or error) → update `queries` row (`completed`/`failed`).
- **Reload:** UI re-fetches `datasets`, `queries`, `audit_log`; nothing is regenerated.
- **Delete (Phase 2):** removing a dataset drops its `ds_<id_safe>` table and the `datasets` row; its `queries`/`audit_log` history is retained or cascade-removed (decided in Phase 2 — out of scope for Phase 1).
