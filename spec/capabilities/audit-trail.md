# Capability: Audit Trail

## What It Does
Records every data operation (CSV ingest and each NL query) as a first-class audit entry with the exact SQL and result metadata, and exposes it via a read API + UI panel.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| operation context | internal | ingest code + query nodes | yes |
| limit / dataset_id filter | query params | `GET /audit` | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| audit entry (operation, sql_text, row_count, columns, duration_ms, success, error, timestamp) | DB row | `audit_log` |
| audit list (newest first) | JSON | `GET /audit` → UI audit panel |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | insert `audit_log` row; read list | audit-write failure is logged but does not fail the parent op |

## Business Rules
- EVERY ingest and EVERY query writes exactly one `audit_log` entry — on success AND on failure.
- The entry stores the exact generated/executed SQL (the SELECT, or an ingest load summary), row count, column names, duration in ms, and success/error.
- The audit list is read-only and ordered newest-first.

## Success Criteria
- [ ] After one ingest + one query, `GET /audit` returns at least two entries with correct `operation` values, populated `sql_text`, `duration_ms`, and `success`.
- [ ] A failed query produces an audit entry with `success=false` and a non-null `error_message`.
- [ ] The UI audit panel renders the entries with timestamp, operation badge, and expandable SQL.
