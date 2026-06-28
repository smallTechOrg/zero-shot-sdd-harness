# Data Model — Pandora

SQLite via SQLAlchemy 2.0 (`src/db/models.py`), migrated by Alembic. Two tables in Phase 1; the skeleton's `RunRow`/`runs` table is **replaced** (renamed in place) by these — no second package, no leftover `runs`.

## Entities

### `datasets`
Persisted record of one uploaded file + its profile. The Parquet on disk is the analysis data; this row is its metadata.

| Field | Type | Notes |
|-------|------|-------|
| id | Text PK (uuid) | |
| filename | Text | original upload name |
| storage_path | Text | `data/datasets/<id>.parquet` |
| upload_path | Text | `data/uploads/<id>.<ext>` (raw) |
| row_count | Integer | full count |
| column_count | Integer | |
| profile_json | Text (JSON) | the `DatasetProfile` (schema + per-column metadata + quality flags) — the only dataset info sent to the LLM |
| suggested_questions_json | Text (JSON) | 2–3 suggested questions |
| status | Text | `ready` \| `failed` |
| error_message | Text nullable | parse failure detail |
| created_at / updated_at | TIMESTAMP(tz) | |

### `questions`
One asked question and its full, revisitable record (code · result · cost · timestamps).

| Field | Type | Notes |
|-------|------|-------|
| id | Text PK (uuid) | |
| dataset_id | Text FK → datasets.id | |
| conversation_id | Text nullable | Phase 2 — groups follow-ups; null in Phase 1 |
| question | Text | the user's plain-language question |
| code | Text nullable | the generated (last-attempt) pandas |
| answer_text | Text nullable | markdown plain-language answer |
| chart_spec_json | Text (JSON) nullable | `{type, x, y, series}` for recharts |
| result_json | Text (JSON) nullable | summary table `{columns, rows}` (≤ 200 rows) |
| attempts | Integer | 0 or 1 (Phase 1) |
| prompt_tokens | Integer | sum across LLM calls |
| completion_tokens | Integer | |
| cost_usd | Float | per-question cost |
| model | Text | e.g. `gemini-2.5-flash` |
| status | Text | `completed` \| `stuck` \| `failed` |
| error_message | Text nullable | "what I tried" detail when stuck |
| created_at / updated_at | TIMESTAMP(tz) | |

## Relationships
- `datasets` 1 ──▶ N `questions` (FK `questions.dataset_id`).
- Phase 2: `questions.conversation_id` groups follow-ups within a session.

## Lifecycle
1. **Upload** → `datasets` row created (`status=ready` after profiling, else `failed`); Parquet written to disk.
2. **Ask** → `questions` row created (`status` starts implicit/pending in-runner), graph runs, row updated with code/result/cost/status on completion (`completed`/`stuck`).
3. **Revisit** (Phase 2) → read `questions` by dataset; nothing mutated.
4. **Daily cost** → aggregate `SUM(cost_usd)` over `questions` where `date(created_at) = today`.

## On-disk (not in DB)
- `data/datasets/<id>.parquet` — canonical analysis data (full, typed).
- `data/uploads/<id>.<ext>` — raw upload (for re-profiling).
- `data/agent.db` — SQLite database.
- Raw data **never** leaves disk except as a ready `df` inside the sandbox subprocess; never serialised to the LLM.
