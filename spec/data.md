# Data Model

---

## Storage Technology

SQLite via SQLAlchemy 2.0 + Alembic (the boilerplate's `db/session.py`, `database_url = sqlite:///./data/agent.db`). **SQLite is production here.** Uploaded CSV files live on the local filesystem under `src/data/datasets/<dataset_id>/<filename>` — only metadata + the small profile/sample live in the DB. The existing skeleton `runs` table (migration `0001`) is superseded by the analyst schema below; the new migration adds the analyst columns/tables.

## Entities

### Entity: Dataset

A single uploaded CSV file the user analyzes.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key. |
| filename | Text | yes | Original filename (e.g. `olist_orders_dataset.csv`). |
| path | Text | yes | Local path to the stored file. |
| row_count | Integer | no | Total rows (from profiling). |
| schema_json | Text (JSON) | yes | `[{name, dtype}]` — column names + dtypes (the LLM-safe schema). |
| sample_json | Text (JSON) | yes | ≤ 20 sample rows used only for prompts. |
| profile_json | Text (JSON) | no | Full auto-profile (ranges, distinct, missing). **Phase 2** populates; nullable in Phase 1. |
| uploaded_at | TIMESTAMP(tz) | yes | Upload time. |

### Entity: Run

One question asked against one dataset, with the full code-execution audit trail.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key (the boilerplate `RunRow.id`). |
| dataset_id | Text (FK→Dataset) | yes | Which dataset was analyzed. |
| session_id | Text (FK→Session) | no | Owning session. **Phase 3**; nullable in Phase 1. |
| question | Text | yes | The user's plain-English question. |
| plan | Text | no | Short plan from the `plan` node. |
| steps_json | Text (JSON) | yes | Audit trail: `[{attempt, code, ok, error|null, duration_ms}]` — every code attempt + result/error. |
| answer | Text | no | Final plain-English answer. |
| chart_spec_json | Text (JSON) | no | Plotly JSON chart spec (null if no chart). |
| table_json | Text (JSON) | no | Summary table as JSON records. |
| status | Text | yes | `running` \| `completed` \| `failed`. |
| error_message | Text | no | Last error if failed. |
| tokens | Integer | no | Accumulated LLM tokens. **Phase 1** captures; surfaced in UI **Phase 5**. |
| cost_usd | Real | no | Estimated cost. **Phase 5** computes; nullable until then. |
| followups_json | Text (JSON) | no | 2–3 suggested follow-ups. **Phase 2**; nullable in Phase 1. |
| created_at | TIMESTAMP(tz) | yes | Run start. |
| updated_at | TIMESTAMP(tz) | yes | Last update. |

> Phase 1 reuses the skeleton `runs` table id/status/error/created_at/updated_at columns and **adds** `dataset_id`, `question`, `plan`, `steps_json`, `answer`, `chart_spec_json`, `table_json`, `tokens`, plus the nullable forward-looking columns (`session_id`, `cost_usd`, `followups_json`). The skeleton's generic `input_text`/`output_text` columns are dropped or left unused.

### Entity: Session  *(Phase 3)*

A resumable conversation over a dataset, carrying chat-turn history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key. |
| dataset_id | Text (FK→Dataset) | yes | Active dataset. |
| messages_json | Text (JSON) | yes | Persisted `AgentState.messages` chat history. |
| created_at / updated_at | TIMESTAMP(tz) | yes | Timestamps. |

### Relationships

- **Dataset 1—N Run** — a dataset has many runs (its question history).
- **Session 1—N Run** (Phase 3) — a session groups runs in one conversation.
- **Dataset 1—N Session** (Phase 3) — a dataset can be opened in many sessions.
- **Run N—N Dataset** (Phase 4) — multi-file runs reference multiple datasets via a `run_datasets` join table; `Run.dataset_id` remains the primary/first dataset.

## Data Lifecycle

- **Create:** a Dataset on upload (file written to disk, metadata + schema + sample persisted); a Run on each question.
- **Update:** a Run progresses `running → completed | failed`, accumulating `steps_json`, `answer`, `chart_spec_json`, `table_json`, `tokens`.
- **Delete:** no automatic deletion in v1 (single-user, audit-trail-first). Manual file/DB cleanup only.
- **Archive:** none — full history is the point.

## Sensitive Data

- The CSV files may contain PII — they stay **local** and are never sent to the LLM. Only `schema_json` (column names + dtypes) and `sample_json` (≤ 20 rows) ever reach prompts, by design (see [`spec/agent.md#privacy-boundary`](agent.md#privacy-boundary)). The privacy guarantee is enforced by construction and asserted in tests.
- API keys live in `.env` (`AGENT_GEMINI_API_KEY`), never in the DB.
