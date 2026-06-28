# Data Model

## Storage Technology

SQLite via SQLAlchemy 2.0 + Alembic. SQLite is the production database (single-user, single-machine; no concurrency). Uploaded file bytes are stored on local disk under `data/uploads/`; the DB holds metadata, profiles, and the audit trail. See [architecture.md](architecture.md#stack).

## Entities

### Entity: Dataset

An uploaded tabular file in the user's library.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| name | str | yes | Original filename |
| kind | str | yes | "csv" \| "excel" |
| storage_path | str | yes | Local path to stored bytes (never sent to LLM) |
| size_bytes | int | yes | File size |
| row_count | int | no | Rows (computed at profile) |
| created_at | timestamp | yes | Upload time |

### Entity: DatasetProfile

Privacy-safe profile of a dataset (or one Excel sheet). LLM-visible.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| dataset_id | str (fk) | yes | → Dataset |
| sheet_name | str | no | Excel sheet (null for CSV) |
| schema_json | json | yes | Column names + dtypes |
| profile_json | json | yes | Per-column: min/max/mean/missing count/distinct count/top categories. **No raw rows.** |
| created_at | timestamp | yes | |

### Entity: Session

A conversation thread over one or more datasets.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| title | str | no | Auto/derived title |
| created_at | timestamp | yes | |
| updated_at | timestamp | yes | |

### Entity: Query (audit trail / run)

One question→answer turn. Extends the existing `RunRow` concept.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key (= run_id) |
| session_id | str (fk) | yes | → Session |
| dataset_id | str (fk) | yes | → Dataset (primary dataset) |
| question | str | yes | User question |
| plan | str | no | Generated plan |
| code | str | no | Generated pandas executed locally |
| result_json | json | no | Structured result (scalar/table/chart-spec) |
| answer | str | no | Plain-language answer |
| status | str | yes | pending/completed/failed |
| error_message | str | no | On failure |
| prompt_tokens | int | no | Cost meter (Phase 2) |
| completion_tokens | int | no | Cost meter (Phase 2) |
| cost_usd | float | no | Estimated cost (Phase 2) |
| created_at | timestamp | yes | |

### Relationships

- Dataset 1—N DatasetProfile (one per sheet for Excel; one for CSV).
- Session 1—N Query.
- Dataset 1—N Query (a query references its primary dataset; Phase 3 adds multi-dataset linkage).

## Data Lifecycle

- **Create:** Dataset + DatasetProfile on upload; Session on first query (or explicit new session); Query per question.
- **Update:** Query updated as the graph progresses (plan→code→result→answer→status); Session.updated_at on each query.
- **Delete:** Dataset delete (Phase 3) cascades profiles and removes stored bytes; queries retained for audit unless the dataset is purged.
- **Retention:** all persisted indefinitely (personal audit trail); no time-boxing in v1.

## Sensitive Data

The uploaded file bytes (`storage_path`) contain the sensitive raw data. They live only on local disk and are **never** read into any LLM-bound payload. Only `schema_json`, `profile_json`, and result *summaries* are LLM-visible. No external transmission of rows under any path — enforced in [agent.md](agent.md) and tested.
