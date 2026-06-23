# Capability: Upload CSV to Table

## What It Does
Ingests one uploaded CSV file into a real, queryable SQLite table and caches its schema + a tiny row sample for token-economical prompting.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | CSV (multipart) | `POST /datasets` upload | yes |
| name | string | form field (defaults to filename) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset metadata (id, name, table_name, row_count, columns) | JSON | API response → UI dataset card |
| `datasets` row | DB row | SQLite |
| `ds_<id>` data table | dynamic table | SQLite |
| cached schema_text + sample_text + columns_json | text/JSON | `datasets` row |
| audit entry (op `ingest`) | DB row | `audit_log` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | create `datasets` row, create `ds_<id>` table, bulk insert, write audit | `INGEST_FAILED` (500); audit records failure |

## Business Rules
- CSV must have a header row; column names are sanitized to valid SQL identifiers.
- Type inference per column → SQLite affinity `INTEGER` / `REAL` / `TEXT`; empty cells → `NULL`.
- Sample cached at ingest is ≤ 20 rows; schema cached as `{name,type}` list — these (not full rows) feed the LLM later.
- Table name = `ds_` + the dataset UUID with hyphens replaced by underscores.
- Every ingest (success or failure) writes one `audit_log` entry.

## Success Criteria
- [ ] Uploading a valid CSV returns dataset metadata with correct columns + row_count and creates a queryable `ds_<id>` table whose row count matches the file.
- [ ] An empty or header-less CSV returns `BAD_CSV`/`EMPTY_FILE` (400), not a 500/crash.
- [ ] After ingest, the `datasets` row has non-empty `schema_text` and `sample_text` (≤ 20 rows), and an `audit_log` op `ingest` entry exists with `duration_ms` and `success=true`.
