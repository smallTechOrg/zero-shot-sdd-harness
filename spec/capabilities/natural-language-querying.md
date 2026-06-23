# Capability: Natural Language Querying

## What It Does

Translates a user's natural-language question into DuckDB SQL via Gemini 2.5 Flash tool-use, executes the SQL against the session's uploaded datasets, and streams the result back over Server-Sent Events.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `session_id` | string (UUID) | `GET /chat` query param | Yes |
| `q` | string | `GET /chat` query param | Yes |
| Conversation history | list of `{role, content}` | SQLite `messages` table (last 10 messages) | No |
| Dataset schema context | compact schema string | Built by `build_schema_context` node from SQLite `datasets` records | Derived |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| SSE `status` events | `{node, message}` JSON | SSE stream to browser |
| SSE `chunk` events | `{text}` JSON | SSE stream to browser (incremental markdown tokens) |
| SSE `table` event | `{columns, rows, row_count}` JSON | SSE stream to browser |
| SSE `chart` event | `ChartSpec` JSON | SSE stream to browser |
| SSE `done` event | `{message_id, status}` JSON | SSE stream to browser |
| User message | `Message` SQLite row (role=user) | SQLite `messages` table |
| Assistant message | `Message` SQLite row (role=assistant, content=RichResponseModel JSON) | SQLite `messages` table |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | SELECT datasets, messages (history) for session | SSE `error` event; status=failed |
| Gemini 2.5 Flash | `classify_intent` — label question type | SSE `error` event; status=failed |
| Gemini 2.5 Flash | `call_llm_with_tools` — generate SQL via tool-use | SSE `error` event; status=failed |
| DuckDB (in-memory) | Execute SQL via `execute_query` node | SSE `error` event with user-friendly message; status=failed |
| Gemini 2.5 Flash | `format_response` — generate narrative + ChartSpec JSON | Falls back to text-only response (chart omitted) |
| SQLite | INSERT/UPDATE message records | Non-fatal; log warning |

## Business Rules

- The LLM prompt must never contain raw dataset rows — schema context is column names, types, and row count only.
- Schema context is capped: if total schema string exceeds 4000 characters, truncate each dataset to 20 columns with a `[...N more]` suffix.
- Conversation history is the last 10 messages (5 user + 5 assistant turns) from the session's `messages` table.
- The `execute_sql` tool is the only tool declared to Gemini — the model must use it to answer data questions.
- If the model returns plain text (no tool call), the response is treated as a clarification and streamed as narrative only (no table, no chart).
- DuckDB query results are capped at 500 rows. The full `row_count` is reported in the `table` event.
- Chart auto-selection rules:
  - 1 numeric column, ≤20 rows, non-date grouping → bar chart
  - Date/time column in result → line chart
  - 2 columns (label + value), ≤8 rows → pie chart
  - All other cases → no chart (table only)
- `off_topic` questions receive a canned "I can only answer questions about your uploaded datasets" response.
- The user question and assistant response are always persisted to SQLite after the SSE stream completes (success or failure).

## Success Criteria

- [ ] Uploading a CSV and asking "What are the top 5 rows by [numeric column]?" returns a correct SQL-backed answer with a table within 10 seconds.
- [ ] The SSE stream delivers `status`, `chunk`, `table`, `done` events in that order; the frontend renders them progressively.
- [ ] The LLM prompt logged (via structlog) never contains raw row data — only schema metadata.
- [ ] An off-topic question returns a canned clarification response (no SQL executed, no chart).
- [ ] A question with a misspelled column name results in an SSE `error` event with a user-friendly message and `status=failed`; the message is saved to SQLite.
- [ ] Conversation history from prior turns is included in the prompt (verified by asking a follow-up question that references the previous answer).
- [ ] After 10 turns, only the last 10 messages are included in context (history capping).
