# Capability: SQL / Data Audit Log

## What It Does

Records every SQL query the analyst agent executes via DuckDB, capturing the timestamp, dataset name, SQL text, row count returned, execution latency, and any error — providing a complete audit trail of all data operations.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `session_id` | string (UUID) | `AnalystState` | Yes |
| `message_id` | string (UUID) | `AnalystState` | Yes |
| `sql` | string | `AnalystState.sql` (from `call_llm_with_tools`) | Yes |
| `dataset_name` | string | Primary dataset in the query (from `AnalystState.datasets`) | Yes |
| `row_count` | integer | DuckDB result count | No (absent on error) |
| `latency_ms` | integer | Wall clock: query start → end | No (absent on error) |
| `error` | string | DuckDB exception message | No (absent on success) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `QueryLog` record | SQLite row | `query_logs` table |
| Audit log list | paginated `QueryLog` JSON | `GET /audit` response |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | INSERT `query_logs` row | Non-fatal: log warning with `structlog`; do not fail the query response |
| SQLite | SELECT `query_logs` (for `GET /audit`) | Return 500 |

## Business Rules

- Every `execute_query` node invocation writes exactly one `QueryLog` row, regardless of success or failure.
- If DuckDB execution fails, `error` is set and `row_count` / `latency_ms` are null.
- Audit insert failure is non-fatal — a structlog warning is emitted but the query response proceeds normally.
- `dataset_name` is the first dataset name referenced in the SQL FROM clause, or "multiple" if the SQL joins more than one view. This is a heuristic based on the registered view names, not SQL parsing.
- `latency_ms` is measured as the wall-clock time from before `duckdb.execute()` to after the result fetch, in milliseconds.
- `GET /audit` returns entries for a single `session_id` only. Cross-session audit is not supported.
- `GET /audit` default limit is 50; maximum 200. Entries are ordered by `created_at` descending (newest first).
- In Phase 1, the audit log is stored and readable via the API (`GET /audit`), but the UI shows a stub panel. The backend is fully functional.

## Success Criteria

- [ ] After each chat query, `GET /audit?session_id=<id>` returns a new entry with the correct `sql`, `dataset_name`, `row_count`, and `latency_ms` (latency > 0).
- [ ] A failed DuckDB query produces a `QueryLog` row with `error` set and `row_count` null.
- [ ] `GET /audit` without `session_id` returns 400.
- [ ] `GET /audit?session_id=<id>&limit=5` returns at most 5 entries.
- [ ] `GET /audit?session_id=<id>&offset=5` returns entries starting from the 6th newest.
- [ ] An audit insert failure (simulated by monkeypatching SQLite) does not cause the chat response to fail — the SSE stream completes normally.
- [ ] Audit entries persist across server restarts (SQLite file on disk).
