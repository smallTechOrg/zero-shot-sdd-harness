# Data Model

---

## Storage Technology

SQLite (production DB for this single-local-user tool) at `AGENT_DATABASE_URL=sqlite:///./data/agent.db`, via SQLAlchemy 2.0 declarative models and Alembic migrations. Uploaded source files are stored on the local filesystem under `data/datasets/`; the DB stores their paths and profiles, not their raw rows. JSON-shaped fields (profile, result, chart, key numbers, table) are stored as `Text` holding serialized JSON, matching the skeleton's `Text`-column convention.

## Entities

### Entity: Dataset  *(Phase 1)*

An uploaded spreadsheet plus its auto-profile. The unit the user asks questions about.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| name | str | yes | Display name (defaults to the original filename stem; renamable — deferred) |
| original_filename | str | yes | The uploaded file name |
| file_path | str | yes | Local path to the stored file (`data/datasets/<id>.<ext>`) |
| file_format | str | yes | `csv` or `xlsx` |
| size_bytes | int | yes | Stored file size (enforces the ~100 MB limit) |
| row_count | int | yes | Exact number of data rows |
| column_count | int | yes | Number of columns |
| profile_json | str (JSON) | yes | `{columns: [{name, dtype, null_count, sample_values}], quality_flags: [...], sample_rows: [...]}` |
| created_at | datetime | yes | Upload time |

### Entity: Run  *(Phase 1; extended in Phase 2)*

One question asked against one dataset, with everything needed to display and audit the answer. Doubles as the history record.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| dataset_id | str (fk → Dataset.id) | yes | Which dataset was analysed |
| session_id | str (fk → Session.id) | no | Owning session (Phase 2; null in Phase 1) |
| question | str | yes | The user's plain-language question |
| status | str | yes | `pending` \| `running` \| `completed` \| `failed` |
| generated_code | str | no | The exact pandas that ran (final attempt) |
| result_json | str (JSON) | no | Aggregated `{value, table, columns}` from execution |
| answer_text | str | no | Plain-language answer with key numbers |
| narrative | str | no | Short interpretation |
| key_numbers_json | str (JSON) | no | `[{label, value}, ...]` |
| chart_json | str (JSON) | no | Vega-Lite spec |
| table_json | str (JSON) | no | Summary table rows |
| attempts | int | yes | Generate→execute attempts (retry count), default 0 |
| tokens_used | int | no | Total tokens (Phase 2) |
| cost_estimate_usd | float | no | Estimated cost (Phase 2) |
| error_message | str | no | Failure detail if `status=failed` |
| created_at | datetime | yes | When the question was asked |
| updated_at | datetime | yes | Last update (on finalize/error) |

### Entity: Session  *(Phase 2)*

A working conversation over one loaded dataset — groups runs and carries turn memory for follow-ups.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| dataset_id | str (fk → Dataset.id) | yes | The loaded dataset |
| title | str | no | Auto-derived from the first question |
| created_at | datetime | yes | Session start |
| updated_at | datetime | yes | Last activity |

### Relationships

- `Dataset 1—* Run` — a dataset has many runs (its question history). `Run.dataset_id` → `Dataset.id`.
- `Dataset 1—* Session` *(Phase 2)* — a dataset has many sessions.
- `Session 1—* Run` *(Phase 2)* — a session groups its runs in order; `Run.session_id` → `Session.id` (nullable, Phase-1 runs have none).

## Data Lifecycle

- **Create:** a `Dataset` row + stored file on upload; a `Run` row when a question is asked (`running`), finalized to `completed`/`failed`.
- **Update:** a `Run` is updated once at finalize/error. `Dataset` is otherwise immutable in Phase 1 (rename/annotate deferred).
- **Delete:** none in Phase 1 (no delete UI). Datasets and runs persist across days on the local disk — this is the "persistent workspace" the vision calls for.
- **Re-run** *(Phase 2)*: re-running a saved `Run` creates a **new** `Run` row against the current dataset — the original is never mutated.

## Sensitive Data

The user's raw data is private but stays entirely local (files under `data/`, SQLite on disk). **Only** schema, sample rows, aggregated results, and the question are sent to Gemini — enforced by the graph design (`load_context` never loads full rows into state; `execute_code` runs in a subprocess whose raw data never enters an LLM prompt). No auth/PII handling beyond keeping everything on the single local machine. The Gemini API key lives in `.env` (git-ignored), read via `AGENT_GEMINI_API_KEY`.
