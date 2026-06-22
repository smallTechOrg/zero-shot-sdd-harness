# Capability: Dataset Management

## What It Does

Lets a user upload CSV/Parquet files into a session, registers each as a queryable DuckDB table plus a metadata record (with cached schema + sample rows), and lists the datasets in the session.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|---------|
| session_id | int | Active session (from `02`/`05`) | yes |
| file | uploaded file (CSV or Parquet) | User upload via web UI | yes |
| dataset_name | string | User-provided, or derived from filename | no (defaults to filename stem) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Dataset record | row in metadata DB (`Dataset`) | SQLite metadata store |
| DuckDB table | table holding the file's rows | DuckDB analytical store |
| Cached schema | JSON (column names + types) | `Dataset.schema_json` in metadata DB |
| Cached sample rows | JSON (≤ N rows) | `Dataset.sample_rows_json` in metadata DB |
| Dataset list | list of Dataset records | Web UI (session view, left panel) |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| DuckDB | Ingest file into a session-scoped table; introspect schema; SELECT a small sample | Reject the upload with a user-facing error (unparseable/unsupported file); do not create the Dataset record; write a failure audit entry |
| SQLite metadata DB | Insert/list `Dataset` rows | Abort the request (500); file ingestion is rolled back so no orphan table is left |

## Business Rules

- Only **CSV** and **Parquet** are accepted in v0.1. Other types are rejected with a clear message.
- Each dataset maps to exactly one DuckDB table, named deterministically and **scoped to its session** so two sessions can reuse a name without collision.
- On registration, the schema (column names + types) and **at most N sample rows** (N small, configurable, e.g. 5) are introspected once and **cached** in the metadata DB. These caches — not the raw data — are what later feed the LLM.
- **No LLM call happens during upload.** Registration is pure ingestion + introspection.
- User datasets are stored and queried **locally only**; raw rows never leave the machine.
- Datasets persist across restarts (the session, its DuckDB tables, and metadata all survive).
- Dataset table access for querying is **read-only**; this capability is the only writer of user data, and only at ingest time.

## Success Criteria

- [ ] Uploading a CSV creates a `Dataset` row and a queryable DuckDB table whose row count matches the file.
- [ ] Uploading a Parquet file works identically to CSV.
- [ ] After upload, `schema_json` and `sample_rows_json` are populated and `len(sample_rows) ≤ N`.
- [ ] Two datasets with the same filename in two different sessions do not collide.
- [ ] Uploading an unsupported/corrupt file returns a clear error and creates no Dataset row and no orphan DuckDB table.
- [ ] Listing datasets for a session returns exactly the datasets uploaded to it.
- [ ] After a process restart, previously uploaded datasets are still listed and queryable.
