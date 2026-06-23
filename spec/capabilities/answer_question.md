# Capability: Answer Question

## What It Does
Turns a natural-language question into a read-only SQL query, runs it, and returns a formatted analyst answer plus the result rows.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | `POST /sessions/{id}/ask` | yes |
| session_id | string | path | yes |
| schema summary + 5-row sample + recent history | derived | Slice A helpers + DB | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text | string | API response + qa_turns |
| sql_text | string | API response + qa_turns |
| result | `{columns, rows}` | API response + qa_turns |
| qa_turns row | DB row | DB |
| audit_log row | DB row (operation="query") | DB |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | generate SQL, format answer | set error → turn status="failed" |
| SQLite | run read-only query | set error → turn status="failed", audit-logged |

## Business Rules
- The prompt contains ONLY the compact schema, a 5-row sample, and the last 3 Q&A pairs — never the full table.
- Only a single read-only statement may run (see [enforce_read_only](enforce_read_only.md)).
- Every query attempt is audit-logged with rows_returned and success/error.

## Success Criteria
- [ ] An aggregation question returns prose grounded in the result rows + the rows themselves.
- [ ] The SQL used is returned and persisted on the turn.
- [ ] A `qa_turns` row and an `audit_log` row (`operation="query"`) are written.
- [ ] An LLM or SQL error yields `status="failed"` with a surfaced message, no crash.
