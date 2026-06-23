# Capability: Ingest Dataset

## What It Does
Materializes an uploaded CSV/Excel file as a real, read-only SQLite table within a session.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | bytes (CSV/.xlsx) | `POST /datasets` multipart | yes |
| filename | string | upload | yes |
| session_id | string | form field (optional) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset summary | `{session_id, dataset_id, table_name, row_count, columns[]}` | API response |
| data table `ds_<id>` | SQLite table | production SQLite DB |
| datasets + sessions rows | DB rows | DB |
| audit_log row | DB row (operation="ingest") | DB |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | CREATE TABLE + INSERT rows | 400/500, no partial table left committed |

## Business Rules
- Column types inferred from the data (TEXT/INTEGER/REAL).
- The created data table is never written again after ingest.
- A new session is created when `session_id` is absent; otherwise the dataset attaches to it.
- The ingest operation is audit-logged.

## Success Criteria
- [ ] Uploading a valid CSV returns the correct `row_count` and column list.
- [ ] A `ds_<id>` table with the ingested rows exists in the SQLite DB.
- [ ] An `audit_log` row with `operation="ingest"`, `success=true` is written.
- [ ] An invalid/empty file returns 400 and creates no data table.
