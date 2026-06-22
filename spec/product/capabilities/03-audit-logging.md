# Capability: Audit Logging

## What It Does

Persists a durable record of every SQL/data operation the agent performs — capturing the originating NL prompt, the generated SQL, the row count, the duration, and a timestamp — and exposes it for viewing in the UI.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|---------|
| session_id | int | Active session | yes |
| nl_prompt | string | The user question that triggered the op | yes (may be null for non-NL ops) |
| generated_sql | string | Output of `generate_sql` (or the ingest SQL) | yes (when SQL ran) |
| row_count | int | Result of `execute_sql` | yes (when SQL ran; null on failure) |
| duration_ms | int | Measured around the data op | yes |
| status | enum (`success` / `error`) | Set by the writer | yes |
| error_message | string | Present on failure | no |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| AuditLogEntry record | row in metadata DB | SQLite metadata store |
| Audit log view | reverse-chronological list of entries | Web UI (audit panel/tab, see `06`) |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite metadata DB | Insert `AuditLogEntry`; query entries by session | Log-write failure is logged to stdout and does not abort the user's request (audit is best-effort-durable but must never crash the primary flow); read failure → 500 on the audit view only |

## Business Rules

- **Every** SQL/data operation is logged — both successful queries and failures. A query that runs without an audit entry is a bug.
- Each entry records, at minimum: timestamp, session_id, NL prompt, generated SQL, row count, duration (ms), and status.
- Failures (invalid SQL, LLM error, rejected upload) are logged with `status=error` and an `error_message`.
- Audit entries are **append-only** — never edited or deleted within v0.1.
- The audit log is **viewable in the UI**, scoped to the current session, newest first.
- Writing the audit entry must not be able to crash the request that triggered it (best-effort durability; failure is logged, not propagated).

## Success Criteria

- [ ] Every successful NL query produces exactly one `success` audit entry with non-null nl_prompt, generated_sql, row_count, and duration_ms.
- [ ] A failed query (bad SQL or LLM error) produces an `error` audit entry with an error_message.
- [ ] A rejected/failed dataset upload produces an `error` audit entry.
- [ ] The audit view returns entries for the current session in reverse-chronological order.
- [ ] Audit entries persist across a process restart.
- [ ] No code path executes SQL against user data without writing a corresponding audit entry.
