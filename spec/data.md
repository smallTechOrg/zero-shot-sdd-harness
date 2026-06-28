# Data Model

SQLite via SQLAlchemy + Alembic. Phase 1 introduces two tables. The skeleton's `runs` table is
superseded by `analyses` (the run-history audit); `datasets` is new.

## Entities (Phase 1)

### `datasets`

Uploaded file metadata + computed profile.

| Field | Type | Notes |
|-------|------|-------|
| `id` | Text (UUID) | PK |
| `filename` | Text | original upload name |
| `storage_path` | Text | local path to the saved file (not exposed to LLM) |
| `row_count` | Integer | total rows |
| `column_count` | Integer | total columns |
| `profile` | JSON (Text) | columns: name, dtype, min/max or top values, missing_count, distinct_count; plus the bounded row sample |
| `size_bytes` | Integer | file size |
| `created_at` | TIMESTAMP (tz) | UTC |

### `analyses`

The run-history audit — one row per query.

| Field | Type | Notes |
|-------|------|-------|
| `id` | Text (UUID) | PK |
| `dataset_id` | Text | FK → `datasets.id` |
| `question` | Text | plain-language question |
| `code` | Text | exact generated pandas code that produced the answer |
| `result` | JSON (Text) | serialized execution result (the numbers) |
| `chart_spec` | JSON (Text) | Vega-Lite spec, nullable |
| `answer` | Text | prose answer |
| `steps_taken` | Integer | loop iterations used |
| `status` | Text | `running` \| `completed` \| `failed` |
| `error_message` | Text | nullable; populated on `failed` |
| `created_at` | TIMESTAMP (tz) | UTC |
| `updated_at` | TIMESTAMP (tz) | UTC |

## Relationships

- `datasets` 1 ── N `analyses` (each analysis runs against one active dataset).

## Lifecycle

- **Upload:** `datasets` row created with profile; file saved to `storage_path`.
- **Ask:** `analyses` row created with `status=running`.
- **Complete:** row updated to `completed` with `code`, `result`, `chart_spec`, `answer`,
  `steps_taken`.
- **Fail:** row updated to `failed` with `error_message` and the last attempted `code` — the
  audit record persists either way.
- Rows are immutable after terminal status (audit trail).

## Deferred (later phases)

- `sessions` + turn memory (Phase 2), `annotations` (Phase 3), `derived_datasets` /
  library (Phase 3), `costs` / token accounting (Phase 4). Not modeled in Phase 1.
