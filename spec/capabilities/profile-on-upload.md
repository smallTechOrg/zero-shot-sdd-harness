# Capability: Profile on Upload

## What It Does
Ingests an uploaded CSV into a local DuckDB table and returns an auto-profile (row count, per-column type, null/distinct counts, numeric ranges) — all locally, with no LLM call.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | CSV upload (multipart) | Browser uploader | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset | Dataset record (id, name, row_count, columns, profile, status) | SQLite + browser profile card |
| duckdb table | local DuckDB file | `data/duckdb/{id}.duckdb` (stays on machine) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| DuckDB (local) | `read_csv_auto` ingest + schema/profile queries | dataset `status="failed"`, error message surfaced; no LLM involved |

## Business Rules
- CSV only in Phase 1 (Excel rejected with a clear message — stub).
- Handle messy data: rely on DuckDB type inference; report nulls/distincts so the user sees data health.
- Up to ~100MB; profile completes under ~30s.
- No raw rows are sent anywhere off-machine; profiling is local SQL only.

## Success Criteria
- [ ] Uploading a valid CSV returns a profile with the correct row count and one entry per column (name + DuckDB type).
- [ ] The profile reports null counts and distinct counts per column, and min/max for numeric columns.
- [ ] A non-CSV or unparseable file returns a 400/500 with a clear message, not a crash.
- [ ] A ~100MB CSV profiles in under ~30s.
