# Data Model

---

## Storage Technology

SQLite via SQLAlchemy 2.0 + Alembic (the boilerplate skeleton's `AGENT_DATABASE_URL`). Local-first, single-user — SQLite is the deliberate fit, not a substitute. Raw dataset bytes live on the local filesystem (a datasets directory); the database stores only metadata, derived profiles, and the analysis audit trail.

The skeleton ships a `runs` table ([RunRow](../src/db/models.py)). This spec ADDS the entities below via Alembic migrations; the legacy `runs` table may remain unused or be folded into `Turn`.

## Entities

### Entity: Dataset

A profiled file in the user's library.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| name | str | yes | Display name (defaults to filename) |
| file_path | str | yes | Absolute path to the stored file on disk |
| source_kind | str | yes | "csv" \| "excel" (excel later phase) |
| row_count | int | yes | Computed locally over the full file |
| column_count | int | yes | Number of columns |
| profile | JSON | yes | Per-column profile (types, ranges, nulls, distinct, sample_values) |
| sample_rows | JSON | yes | First N (=5) rows for LLM context |
| derived_from | str (uuid) \| null | no | Source dataset id if this is a saved derived dataset (later phase) |
| created_at | datetime | yes | Upload time |

### Entity: Conversation

A back-and-forth session bound to one dataset (or a join set, later phase).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| dataset_id | str (uuid) | yes | FK → Dataset |
| title | str | no | Auto-derived from first question |
| created_at | datetime | yes | Start time |

### Entity: Turn

One question→answer exchange. Immutable audit record.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| conversation_id | str (uuid) | yes | FK → Conversation |
| question | str | yes | The user's natural-language question |
| plan | JSON | no | Step list the agent planned |
| code | str | no | Exact pandas/DuckDB code executed locally |
| result_table | JSON | no | Computed result (display-capped) |
| answer | str | no | Direct natural-language answer |
| chart_spec | JSON | no | Chosen chart type + axes |
| follow_ups | JSON | no | 2-3 suggested follow-up questions |
| prompt_tokens | int | no | LLM prompt tokens |
| completion_tokens | int | no | LLM completion tokens |
| estimated_cost_usd | float | no | Estimated cost of this turn |
| status | str | yes | "completed" \| "failed" |
| error_message | str \| null | no | Set on failure |
| created_at | datetime | yes | Turn time |

### Relationships

- Dataset 1—N Conversation (one dataset, many conversations).
- Conversation 1—N Turn (ordered by `created_at` — this ordered list IS the conversation history fed back to the LLM).
- Dataset 0..1—N Dataset via `derived_from` (a saved derived dataset points to its source).

## Data Lifecycle

- **Created:** Dataset on upload+profile; Conversation on first question for a dataset; Turn on every answer.
- **Updated:** Turn rows are write-once (immutable audit). Dataset `name` may be renamed.
- **Deleted:** User may delete a dataset (removes file + cascades conversations/turns) — later phase. No automatic archival; the library persists indefinitely.

## Sensitive Data

The raw data files are the sensitive asset. They never leave the machine and are never sent to the LLM (see [privacy boundary](../architecture.md#privacy-boundary)). The DB stores only profiles, samples (N rows), and audit records. No secrets are stored in the DB; the Gemini key lives in `.env` as `AGENT_GEMINI_API_KEY`.
