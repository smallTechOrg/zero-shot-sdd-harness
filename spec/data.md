# Data Model

---

## Storage Technology

SQLite (`sqlite:///./data/agent.db`) via SQLAlchemy 2.0 + Alembic — this is the production database for a local, single-user personal tool (there is no PostgreSQL). **Raw CSV rows are NOT stored in the database.** Raw files live on the local filesystem under `data/datasets/{dataset_id}.csv`; SQLite holds only metadata, schema, and run history. This split is the storage-level expression of the privacy boundary (see [architecture.md](architecture.md#the-privacy-data-boundary-first-class-architectural-concern)).

## Entities

### Entity: DatasetRow

Metadata for one uploaded CSV. The raw rows are never a field here — only the derived schema.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key; the `dataset_id` returned to the client |
| filename | str | yes | Original upload filename (display only) |
| row_count | int | yes | `len(df)` computed locally at upload |
| schema_json | str (JSON) | yes | Serialized list of `{name, dtype, friendly_dtype}` — column metadata only, no values |
| created_at | datetime (tz) | yes | Upload time |
| updated_at | datetime (tz) | yes | Last touch |

> The raw file path is derived deterministically (`data/datasets/{id}.csv`), so no path field is stored.

### Entity: DataProfile (in-memory, NOT persisted)

The compact derived artifact the agent computes locally and is the ONLY data-bearing object allowed near the LLM prompt. Computed on demand by `load_profile`; never written to the DB and never contains raw rows.

| Field | Type | Description |
|-------|------|-------------|
| row_count | int | Number of rows |
| columns | list of `{name, dtype, friendly_dtype}` | Schema |
| stats | dict per column | Numeric: min/max/mean/median/std/null_count; categorical: distinct_count, top values + counts; capped |
| examples | dict per column | ≤5 truncated example values per column (each value string-capped) |
| group_aggregates | dict (derived, capped, NOT persisted) | Derived scalars enabling grouped / cross-column-derived / multi-role answers. Holds ONLY aggregate scalars — never raw rows, never a full column — and is never written to the DB. Two blocks (see below). |

**`group_aggregates` structure** — a derived, capped, in-memory artifact consistent with the privacy boundary in [architecture.md](architecture.md#the-privacy-data-boundary-first-class-architectural-concern). It carries derived scalars only:

- **`groups`** — for each grouping key (a categorical column, **including high-cardinality keys** such as team names) × each numeric column, the per-group aggregates `{sum, count, mean, ratio}` (where `ratio` is a cross-column derived metric, e.g. sum ÷ count). The cap is **top-N groups BY THE RELEVANT METRIC** — high-cardinality keys are ranked and truncated to the top-N, **not dropped**. Each grouping carries truncation markers `{total_groups, truncated}` so the model knows the list is a top-N slice.
- **`entity_unions`** — multi-role unions: when the same entity appears across more than one column (e.g. `team1`/`team2` paired with the metric columns `score1`/`score2`), the roles are unioned into per-entity aggregates `{total, count, ratio}` (e.g. goals, matches, goals-per-match). Entities are ranked by `ratio` among those meeting a minimum count (> **Assumed:** 3), then top-N capped with truncation markers `{total_entities, truncated}`. **Empty (`[]`/`{}`) when the dataset has no detectable multi-role column pairs.**

> All `group_aggregates` values are derived scalars computed locally by `load_profile`; the raw DataFrame stays in the node's local scope. Nothing in this artifact is persisted to SQLite.

### Entity: RunRow (extends skeleton)

One question→answer run. Reuses the skeleton's `runs` table, repurposing fields for this domain.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key; the `run_id` |
| dataset_id | str | yes (new column) | FK-by-convention to `DatasetRow.id` |
| input_text | str | yes | The user's question (reuses skeleton column) |
| output_text | str \| null | no | The plain-English answer (reuses skeleton column) |
| status | str | yes | `pending` \| `completed` \| `failed` |
| error_message | str \| null | no | Human-readable error on failure |
| created_at / updated_at | datetime (tz) | yes | Timestamps |

### Relationships

- `RunRow.dataset_id` → `DatasetRow.id` (many runs per dataset). Enforced by convention (single-user local tool); a missing dataset surfaces as a `failed` run with human copy, not a DB constraint error.

## Data Lifecycle

- **Create:** `DatasetRow` + raw file written on upload; `RunRow` written per ask.
- **Update:** `RunRow.status`/`output_text`/`error_message` updated when the run finishes.
- **Delete:** none in Phase 1 (personal tool; the user can delete `data/` manually). Dataset deletion UI is deferred.
- **Time-boxing:** none.

## Sensitive Data

- The **raw CSV** may contain anything the user uploads (potentially PII). It is the protected asset: it stays on local disk and is **never** transmitted to Gemini or persisted in the DB. Only the derived `DataProfile` (summary stats + grouped/derived/multi-role `group_aggregates` + truncated examples) and the question cross the boundary — all derived scalars, never raw rows or full columns.
- No auth/secrets stored. The Gemini API key lives in `.env` (`AGENT_GEMINI_API_KEY`), never in the DB.
