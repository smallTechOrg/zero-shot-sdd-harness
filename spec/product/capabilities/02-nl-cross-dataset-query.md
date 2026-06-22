# Capability: Natural-Language Cross-Dataset Query

## What It Does

Translates a user's plain-English question over one or more datasets in a session into a single read-only SQL statement, executes it in DuckDB, and returns a natural-language answer plus the result table.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|---------|
| session_id | int | Active session | yes |
| question | string (natural language) | User, via chat box | yes |
| dataset schemas + samples | JSON (cached) | Metadata DB (`Dataset.schema_json`, `sample_rows_json`) | yes (assembled by service) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| answer_text | string (NL summary) | Chat message (`Message`, role=assistant) + UI |
| result_table | tabular result set (columns + rows) | Rendered inline in chat; row data from DuckDB |
| generated_sql | string | Stored on the assistant `Message` and in the audit entry |
| Audit entry | row in `AuditLogEntry` | Metadata DB (see capability 03) |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini (`gemini-2.5-flash` default; `gemini-2.5-pro` on escalation) | `generate_sql`: schema+samples+question → SQL; `summarize`: question+truncated result → NL answer | Fatal → `handle_error` node: write a failure audit entry, return a friendly error message in chat; app stays up. No API key → stub provider (signalled in UI). |
| DuckDB | `execute_sql`: run the generated read-only SQL | Invalid/failed SQL is caught: write failure audit entry, return an error message; no crash. (Optionally one bounded regenerate-on-error retry — see Business Rules.) |

## Business Rules

- The LLM receives **only** the cached schema + the ≤ N sample rows for the datasets the plan deems relevant — **never raw datasets, never full result sets**. This is the token-economy guarantee and must be assertable from the request payload.
- Generated SQL must be **read-only** (SELECT/aggregation only); statements that would mutate user data are rejected before execution.
- **Aggregation is computed in DuckDB**, not in the model. The model summarizes an already-aggregated, truncated result — it never adds up rows itself.
- A question may reference **one or more** datasets in the session; cross-dataset joins are first-class.
- Model selection follows token economy: **`gemini-2.5-flash`** for routine NL→SQL; escalate to **`gemini-2.5-pro`** only when the plan flags the question as complex.
- The result **table** rendered to the user comes directly from DuckDB output, not from model text, so figures are exact.
- Each question and its assistant answer are persisted as `Message` rows so conversation history survives restarts.
- On a SQL execution error, the agent may perform **at most one** regenerate-and-retry; if it still fails, return the error gracefully. (Bounded to protect token budget.)

## Success Criteria

- [ ] A single-dataset aggregation question (e.g. "total revenue by month") returns a correct answer and table verified against the same SQL run directly in DuckDB.
- [ ] A cross-dataset question that requires a join between two datasets returns a correct joined result.
- [ ] Inspecting the LLM request shows only schema + ≤ N sample rows per relevant dataset — no raw dataset rows and no full result set.
- [ ] An ambiguous/unanswerable question returns a graceful clarifying or error message, not a crash.
- [ ] A question that generates invalid SQL is caught, audited, and surfaced as an error message (after at most one retry).
- [ ] The question and answer persist as messages and reappear after a restart.
