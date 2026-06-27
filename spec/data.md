# Data Model

Local SQLite (`sqlite:///./data/agent.db`) via SQLAlchemy 2.0 + Alembic. Raw uploaded files live on the local filesystem under `data/uploads/`. **Nothing is persisted to any external service.**

## Data-Locality Guarantees

- The raw uploaded file is written to `data/uploads/<dataset_id>.<ext>` on the local filesystem and never transmitted anywhere.
- The parsed dataframe exists only in-process during ingest (to build the profile) and during analysis execution (loaded from the local file). It is never serialized to an external service.
- Only the `schema_summary` (schema + dtypes + a bounded sample/profile) plus the user's question are sent to the Gemini API. The `schema_summary` is bounded (default a few sample rows + per-column summary stats), so even the sample sent out is small and capped.
- All persisted records (dataset metadata, analysis runs, generated code, results) live only in local SQLite.

## Entities

### `datasets`

One row per uploaded file.

| Field | Type | Notes |
|-------|------|-------|
| `id` | TEXT (uuid) PK | |
| `filename` | TEXT | original upload filename |
| `file_format` | TEXT | `csv` (Phase 1); `xlsx` (Phase 2) |
| `local_path` | TEXT | absolute/relative path under `data/uploads/` |
| `row_count` | INTEGER | rows in the parsed dataframe |
| `column_count` | INTEGER | columns in the parsed dataframe |
| `schema_summary` | TEXT | the schema + dtypes + bounded sample/profile sent to the LLM (the ONLY data that may leave the machine) |
| `status` | TEXT | `ready` once parsed; `failed` if parse failed |
| `error_message` | TEXT NULL | parse error if any |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `analyses`

One row per question asked against a dataset (the run/query record). Stores the generated code, result, and steps so they can be re-fetched and shown.

| Field | Type | Notes |
|-------|------|-------|
| `id` | TEXT (uuid) PK | this is the graph `run_id` |
| `dataset_id` | TEXT FK → `datasets.id` | |
| `question` | TEXT | the user's natural-language question |
| `status` | TEXT | `pending` → `completed` / `failed` |
| `generated_code` | TEXT NULL | the executed pandas code (surfaced to the user) |
| `execution_result` | TEXT NULL | string/repr of the computed result value |
| `execution_steps` | TEXT NULL | captured stdout / intermediate steps |
| `answer` | TEXT NULL | plain-language explanation |
| `attempts` | INTEGER | generate→execute cycles run |
| `error_message` | TEXT NULL | terminal error if `status=failed` |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

> The existing baseline `runs` table is superseded by `analyses`. Phase 1 migration `0002_*` adds `datasets` and `analyses`. The legacy `runs` table may be left in place (unused) or dropped by the migration — generator's choice, but it must not be referenced by the new flow.

## Relationships

- `datasets` 1 ──< `analyses` (one dataset, many questions). FK `analyses.dataset_id → datasets.id`.

## Lifecycle

1. **Upload** → `datasets` row created, file saved locally, parsed, profiled → `status=ready` (or `failed`).
2. **Ask** → `analyses` row created `status=pending`; graph runs.
3. **Complete** → `analyses` row updated with `generated_code`, `execution_result`, `execution_steps`, `answer`, `attempts`, `status=completed`.
4. **Fail** (retries exhausted) → `analyses` row `status=failed` with `error_message`; `answer` holds a plain-language failure message.

> **Assumed:** No retention/expiry policy in v1 — local files and rows persist until the user deletes `data/`. Cleanup is out of scope.
