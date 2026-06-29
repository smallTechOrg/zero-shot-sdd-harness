# Capability: Conversational Q&A

## What It Does

The user types a natural-language question about their uploaded data; the agent generates Python/pandas code to answer it, executes the code server-side, and returns a prose answer with an optional Plotly chart. The full conversation history within the session is preserved and used as context for follow-up questions.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| Question text | string | POST /sessions/{session_id}/messages body `content` field | Yes |
| session_id | UUID string | URL path parameter | Yes |
| File profiles (schema + stats) | JSON objects | Loaded from `files` table in SQLite | Yes (at least one file must be uploaded) |
| Conversation history | array of message objects | Last 10 turns loaded from `messages` table in SQLite | No (empty for first turn) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Prose answer | string (`content` field) | API response body + stored in `messages` table |
| Plotly chart spec | JSON dict (`chart_json` field, nullable) | API response body (not stored in DB) |
| User message record | message object | Stored in `messages` table |
| Assistant message record | message object | Stored in `messages` table |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| LLM (Gemini) | Generate Python/pandas code from question + schema context | Return error message to user; do not crash |
| SQLite (session DB) | SELECT last 10 messages for session; INSERT user + assistant messages | Return HTTP 500 |
| Code execution sandbox | exec() the generated code against loaded DataFrames | Catch exception; route to error handling |

## Business Rules

- At least one file must be uploaded to the session before Q&A is available; otherwise return HTTP 400 with message "Please upload a CSV file first"
- LLM prompt includes column names + dtypes + numeric stats + top-5 value_counts for all uploaded files — never raw rows
- Conversation history is trimmed to the last 10 turns (5 user + 5 assistant alternating) to limit token usage
- History is session-scoped only — no cross-session context
- If the generated code raises an exception, a user-friendly error message is returned; the failed attempt is still stored in `messages`
- Ambiguous column references: agent states its assumption inline in the prose answer
- Clarification needed: answer begins with "To answer this precisely, could you clarify..."

## LLM Prompt Strategy

The prompt sent to the LLM for code generation contains these sections in order:

1. System instruction: role, task, available variables (`dfs` dict, `pd`, `np`, `go`, `px`), output variables (`result`, `fig`)
2. Schema context: column names + dtypes for each uploaded file, labelled by filename
3. Stats context: numeric stats (min/max/mean/std/percentiles) and categorical top-5 value_counts — NO raw rows
4. Conversation history: last 10 turns (role + content pairs)
5. Current question

## Success Criteria

- [ ] Ask "show me revenue by month" against a sales CSV → response contains a Plotly bar chart with months on x-axis and revenue on y-axis
- [ ] Ask a follow-up "now show only Q1" → agent uses prior conversation context to filter correctly without re-specifying the dataset
- [ ] Ask about a column that does not exist → agent returns a helpful prose error message; server does not return HTTP 5xx
- [ ] LLM prompt string logged to stdout never contains a raw row value from the CSV (verified by automated test that inspects the prompt)
- [ ] Conversation history for the session contains both user and assistant turns after each exchange
- [ ] First question in a new session (no prior history) answers correctly
