# Capability: Enforce Read-Only

## What It Does
Guarantees the agent can only ever run read queries, via SQL validation AND a read-only DB connection.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| sql | string | generate_sql node | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| validated sql OR rejection | string / SqlNotAllowed | execute_sql / handle_error |
| audit_log row (operation="blocked") | DB row | DB on rejection |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | read-only connection (mode=ro / query_only=ON) | any mutation attempt errors at the driver level too |

## Business Rules
- Allow only a single `SELECT` (or `WITH ... SELECT`) statement.
- Reject INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/REPLACE/ATTACH/DETACH/PRAGMA-write, multiple statements, and comment-hidden DML.
- Defense in depth: validation rejects, and the executor's connection is read-only so even a missed case cannot mutate.
- Every rejection is audit-logged.

## Success Criteria
- [ ] `assert_read_only` returns the SQL for a valid SELECT/WITH query.
- [ ] `assert_read_only` raises `SqlNotAllowed` for DELETE, DROP, UPDATE, INSERT, ALTER, ATTACH, PRAGMA-write, and multi-statement input (unit-tested).
- [ ] A blocked attempt produces an `audit_log` row with `operation="blocked"`, `success=false`.
- [ ] The executor connection rejects a mutation even if the guard were bypassed.
