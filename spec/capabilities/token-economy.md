# Capability: Token Economy

## What It Does

Ensures the analyst agent's LLM prompts remain minimal and cost-efficient by injecting only schema metadata (column names, types, row count) into the context — never raw dataset rows — and by capping conversation history and schema string length.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `datasets` | list of `Dataset` SQLite rows | `build_schema_context` node (SQLite query) | Yes |
| `conversation_history` | list of `{role, content}` dicts | SQLite `messages` table | No |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `schema_context` | compact schema string | `AnalystState.schema_context` → injected into LLM prompt |
| `conversation_history` (capped) | list[dict], max 10 items | `AnalystState.conversation_history` → injected into LLM prompt |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | SELECT datasets.columns_json, datasets.row_count | Fatal — sets state["error"] |
| SQLite | SELECT messages (last 10, ordered by created_at desc) | Non-fatal — proceeds with empty history |

## Business Rules

- **No raw rows in prompts.** The `columns_json` stored in `Dataset` contains only column names and types — not sample values, not any actual data. The `build_schema_context` node reads only `columns_json` and `row_count` from SQLite. DuckDB is not opened during schema context building.
- **Schema string format** (injected into every data-query prompt):
  ```
  Dataset: sales.csv (1234 rows)
    - date: DATE
    - region: VARCHAR
    - revenue: DOUBLE
  ```
  One block per dataset, blank line between datasets.
- **Schema string cap:** If the total schema string exceeds 4000 characters, each dataset is truncated to its first 20 columns with a `[...{N} more columns]` suffix. The row count is always included regardless of truncation.
- **History cap:** Only the last 10 messages from the session are included in the prompt. Fetch is ordered by `created_at` DESC, LIMIT 10, then reversed for chronological order. If fewer than 10 messages exist, all are included.
- **History format:** Each history entry is a `{role: "user"|"assistant", content: str}` dict. For assistant messages, `content` is the `narrative` field from `RichResponseModel` only — not the full JSON (to avoid injecting table data or chart spec into the context).
- **Query result in format_response:** The narrative generation call sends column names and rows (up to 500 rows) of the query result — this is the bounded DuckDB result, not the raw dataset. This is considered acceptable because the query result is derived, aggregated, and bounded.
- The system prompt (`src/prompts/analyst.md`) explicitly instructs the model: "Never fabricate data. Always use the execute_sql tool to retrieve data. Never assume column values."

## Success Criteria

- [ ] Structured logging for every `call_llm_with_tools` invocation captures the prompt text; an assertion in tests confirms no raw data values appear in the prompt (verified by checking the prompt does not contain strings from the dataset's row values).
- [ ] The schema context string for a dataset with 50 columns includes the first 20 columns and a "[...30 more columns]" suffix when the total schema exceeds 4000 characters.
- [ ] After 15 conversation turns, the prompt contains at most 10 messages of history.
- [ ] For assistant history messages, the prompt contains the narrative text only — not the JSON-serialized `RichResponseModel` (which would include table rows).
- [ ] `build_schema_context` completes without opening a DuckDB connection (verified by mocking DuckDB and confirming no call is made during schema context building).
