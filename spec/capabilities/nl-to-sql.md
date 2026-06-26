# Capability: Natural Language to SQL

## What It Does

Converts a natural-language question and a SQLite table schema into a safe SELECT query, executes it, and returns the result rows — covering the `schema_introspection`, `sql_generation`, and `sql_execution` nodes of the pipeline.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `session_id` | UUID string | `POST /query` request body | Yes |
| `question` | string (≥ 1 char, ≤ 2000 chars) | `POST /query` request body | Yes |
| `table_name` | string | Looked up from `UploadSession` via `session_id` | Derived |
| `schema` | `list[{name, type}]` | `schema_introspection` node | Derived |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `sql` | string (SELECT query) | `AgentState`, `QueryRun.sql`, JSON response |
| `rows` | `list[dict]` | `AgentState` (consumed by `chart_selection` + `insight_generation`) |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | `PRAGMA table_info(table_name)` | Fatal error — schema_introspection node sets `state["error"]` |
| Gemini API | `ChatGoogleGenerativeAI.invoke()` with structured output | Fatal error — sql_generation node sets `state["error"]` |
| SQLite | `session.execute(text(sql))` | Fatal error — sql_execution node sets `state["error"]` |

## Business Rules

- Only SELECT queries are permitted. Any generated SQL containing the keywords `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, or `TRUNCATE` (case-insensitive, whole-word match via `\b` regex) is rejected before execution with the error: "SQL safety violation: only SELECT queries are permitted."
- The SQL-generation prompt instructs the model to generate only syntactically valid SQLite SELECT queries. The system prompt explicitly forbids DDL/DML.
- The system prompt includes the full table schema (column names and types) and the table name so the generated SQL references the correct identifiers.
- If `session_id` does not correspond to an `UploadSession` record, the query API returns HTTP 404 before invoking the pipeline.
- An empty result set (`rows = []`) is not an error. The pipeline continues to `chart_selection` and `insight_generation`.
- Result rows are capped at 1000 rows returned to `AgentState` (beyond that, a `LIMIT 1000` is appended to the SQL if no LIMIT is already present). This prevents unbounded memory use.

## Success Criteria

- [ ] A valid question over an uploaded CSV returns a SELECT query that is syntactically valid SQLite SQL.
- [ ] The returned `rows` match the data in the CSV for the answered question (verified by comparing against expected values in the test fixture CSV).
- [ ] A question that would naively produce a mutating query (e.g. "delete all rows where value > 10") results in a "SQL safety violation" error response with HTTP 200 and `status: "failed"` (not a 500).
- [ ] An attempt to inject DDL via the question (e.g. "show me the data; DROP TABLE data") results in the safety violation error.
- [ ] A question about a non-existent column produces a structured SQL error response (not a 500 crash).
- [ ] LangSmith shows a trace span for the `sql_generation` node with input prompt and output SQL visible.
