# Data Model

## Storage Technology

SQLite (`data/agent.db`), accessed via SQLAlchemy 2.0 (sync) with Alembic migrations. SQLite is appropriate for this project: personal use, single user, local-only, no concurrent writes from multiple processes. The database file lives at the path configured in `AGENT_DATABASE_URL` (default: `sqlite:///./data/agent.db`).

## Entities

### Entity: Dataset

Represents a single uploaded CSV file. Created when the user POSTs to `/datasets`. The file itself is stored on the local filesystem at `data/uploads/<id>.csv`; this table stores only metadata.

| Field | Type | Required | Description |
|---|---|---|---|
| id | TEXT (UUID) | yes | Primary key; generated at upload time |
| filename | TEXT | yes | Original filename as uploaded by the user |
| row_count | INTEGER | yes | Number of data rows in the CSV (excluding header) |
| column_names_json | TEXT | yes | JSON array of column names, e.g. `["date","revenue","region"]` |
| file_path | TEXT | yes | Absolute path to the stored CSV file: `data/uploads/<id>.csv` |
| uploaded_at | TIMESTAMP (UTC) | yes | When the record was created |

### Entity: Analysis

Represents a single analysis run: one question asked against one dataset. Created by `POST /analyses`; updated by the `finalize` or `handle_error` node.

| Field | Type | Required | Description |
|---|---|---|---|
| id | TEXT (UUID) | yes | Primary key; generated when the analysis is created |
| dataset_id | TEXT (UUID) | yes | Foreign key → `datasets.id` |
| question | TEXT | yes | The user's natural-language question |
| answer_text | TEXT | no | Plain-English answer from `generate_answer` node; null if failed |
| chart_json | TEXT | no | Plotly figure JSON string; null if no chart was produced or if failed |
| status | TEXT | yes | `"pending"` → `"completed"` or `"failed"` |
| error_message | TEXT | no | Error detail if `status = "failed"` |
| created_at | TIMESTAMP (UTC) | yes | When the analysis was created |
| updated_at | TIMESTAMP (UTC) | yes | Last update time (set by finalize/handle_error) |

### Entity: Run (existing — retained)

The existing `runs` table from the skeleton is retained for backward compatibility. The new analysis pipeline does not write to `runs`; it writes to `analyses`. The `runs` table remains for the `/runs` API routes that were in the skeleton.

| Field | Type | Required | Description |
|---|---|---|---|
| id | TEXT (UUID) | yes | Primary key |
| status | TEXT | yes | `"pending"` / `"completed"` / `"failed"` |
| input_text | TEXT | no | Original text input (skeleton capability) |
| output_text | TEXT | no | Transform output (skeleton capability) |
| error_message | TEXT | no | Error detail |
| created_at | TIMESTAMP (UTC) | yes | Creation time |
| updated_at | TIMESTAMP (UTC) | yes | Last update time |

### Relationships

```
datasets (1) ──────────────────── (many) analyses
  id ←──────────────────────────── dataset_id
```

One dataset can have many analyses (the user can ask multiple questions about the same uploaded CSV).

## Data Lifecycle

- **Dataset:** Created on `POST /datasets`. Never updated after creation. Not automatically deleted. The user can upload as many CSVs as they want; the files persist on disk at `data/uploads/`.
- **Analysis:** Created with `status = "pending"` on `POST /analyses`. Updated to `status = "completed"` (with `answer_text` and `chart_json`) by the `finalize` node, or to `status = "failed"` (with `error_message`) by the `handle_error` node. Not automatically deleted.
- **Run (legacy):** Created and updated by the legacy `/runs` routes; not touched by the analysis pipeline.

## Sensitive Data

- No PII is stored. CSV files uploaded by the user may contain PII at the user's discretion (it is their local machine).
- No API keys or credentials are stored in the database. `AGENT_GEMINI_API_KEY` lives only in `.env` (gitignored).
- The `file_path` column stores local filesystem paths; these are not sensitive but are internal implementation details not exposed in API responses.
- In Phase 2, database connection URLs (which may contain passwords) will be stored in a `connections` table. Passwords will be masked in API responses at that point.
