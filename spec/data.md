# Data Model

## Storage Technology

SQLite, accessed via SQLAlchemy 2.0, at `AGENT_DATABASE_URL` (a local file). This is the production database. Two categories of tables live in it:

1. **Meta tables** (defined as SQLAlchemy models, migrated via Alembic): `runs` (existing), `datasets`, `sessions`, `qa_turns`, `audit_log`.
2. **Data tables** (created dynamically at ingest, one per uploaded file): named `ds_<dataset_id>`, columns mirror the CSV. These are NOT SQLAlchemy models; they are created by `data/ingest.py` and read only.

## Entities

### Entity: Session

Groups one uploaded dataset (Phase 1) with its Q&A history. Persists across restarts.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (uuid) | yes | Primary key |
| title | TEXT | no | Human label (defaults to the uploaded filename) |
| created_at | TIMESTAMP | yes | Creation time |
| updated_at | TIMESTAMP | yes | Last activity |

### Entity: Dataset

One uploaded file materialized as a SQLite data table.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (uuid) | yes | Primary key |
| session_id | TEXT | yes | FK → sessions.id |
| original_filename | TEXT | yes | Uploaded file name |
| table_name | TEXT | yes | The created data table, `ds_<id>` |
| columns_json | TEXT (JSON) | yes | `[{name, type}]` schema summary |
| row_count | INTEGER | yes | Rows ingested |
| created_at | TIMESTAMP | yes | Ingest time |

### Entity: QaTurn

One question→answer exchange in a session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (uuid) | yes | Primary key |
| session_id | TEXT | yes | FK → sessions.id |
| question | TEXT | yes | The user's NL question |
| sql_text | TEXT | no | The SQL the agent ran (null if blocked/failed before exec) |
| answer_text | TEXT | no | The formatted prose answer |
| result_json | TEXT (JSON) | no | `{columns: [...], rows: [[...]]}` |
| status | TEXT | yes | `completed` \| `failed` |
| error_message | TEXT | no | Set on failure |
| created_at | TIMESTAMP | yes | Turn time |

### Entity: AuditLog

One record per SQL/data operation (ingest write + every query attempt, allowed or blocked).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (uuid) | yes | Primary key |
| session_id | TEXT | no | FK → sessions.id (null for pre-session ops) |
| operation | TEXT | yes | `ingest` \| `query` \| `blocked` |
| question | TEXT | no | Originating question (for queries) |
| sql_text | TEXT | no | The SQL text |
| rows_returned | INTEGER | no | Row count returned |
| success | BOOLEAN | yes | Did the operation succeed |
| error_message | TEXT | no | Reason on failure / block |
| created_at | TIMESTAMP | yes | Operation time |

### Relationships

- `Session` 1 — N `Dataset` (Phase 1: exactly 1; Phase 3: N).
- `Session` 1 — N `QaTurn`.
- `Session` 1 — N `AuditLog`.
- Each `Dataset` owns exactly one dynamic data table `ds_<id>`.

## Data Lifecycle

- **Create:** sessions + datasets on upload; data table on upload; qa_turns + audit_log on each ask.
- **Update:** session.updated_at on each turn. Uploaded data tables are never updated (read-only after ingest).
- **Delete:** none in v1 (no delete endpoint). Re-uploading creates a new dataset/session.
- **Archival:** none.

## Sensitive Data

No auth secrets in the DB. Uploaded data may contain user PII; it stays local and is sent to Gemini only as a 5-row sample plus the schema summary (never the full table). The Gemini API key lives in `.env` only, never persisted.
