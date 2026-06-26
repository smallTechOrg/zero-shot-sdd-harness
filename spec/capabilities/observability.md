# Capability: Observability

## What It Does

Emits structured JSON log lines via structlog for every new operation (graph node entry/exit, LLM calls, CSV load, SQL execution) and propagates all LLM calls to LangSmith as distributed trace spans, with zero code changes required at call sites beyond setting three env vars.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `LANGCHAIN_API_KEY` | string | `.env` | Yes (for LangSmith) |
| `LANGCHAIN_TRACING_V2` | `"true"` | `.env` | Yes (enables LangSmith) |
| `LANGCHAIN_PROJECT` | string | `.env` | Yes (LangSmith project name) |
| `AGENT_LOG_LEVEL` | string (`"INFO"` / `"DEBUG"`) | `.env` | No (default: `"INFO"`) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Structured log lines | JSON (stdout) | Terminal / log aggregator |
| LLM call trace spans | LangSmith run record | LangSmith UI |
| Graph node spans | LangSmith run record (child spans) | LangSmith UI |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| LangSmith API | HTTP POST of trace spans (async, fire-and-forget) | Silent — tracing failure never blocks the agent; a warning is logged to stdout |

## Business Rules

- Every new operation in a slice emits exactly one structured log line at `INFO` level via `src/observability/events.py` (`get_logger()`). The log line always includes: `timestamp` (ISO 8601), `level`, `logger_name`, and `event` (a `snake_case` event name). Additional contextual fields are added per operation (see below).
- Required log events:
  - `csv.loaded` — fields: `table_name`, `row_count`, `col_count`, `duration_ms`
  - `node.enter` — fields: `node_name`, `run_id`, `session_id`
  - `node.exit` — fields: `node_name`, `run_id`, `duration_ms`, `status` (`"ok"` or `"error"`)
  - `sql.generated` — fields: `run_id`, `sql_preview` (first 200 chars), `duration_ms`
  - `sql.executed` — fields: `run_id`, `row_count`, `duration_ms`
  - `insight.generated` — fields: `run_id`, `insight_length`, `duration_ms`
  - `chart.selected` — fields: `run_id`, `chart_type`, `data_point_count`
  - `upload.started` — fields: `filename`, `file_size_bytes`
  - `query.received` — fields: `session_id`, `question_length`
- LangSmith tracing is activated entirely through environment variables. No import or decorator is needed in the node code — `langchain-google-genai` and LangGraph integrate with LangSmith automatically when the env vars are set.
- Log output format: `structlog.processors.JSONRenderer()` — one JSON object per line. Do not use `KeyValueRenderer` or plain-text format.
- Secrets (API keys, full SQL with potential PII) are never logged. SQL is truncated to 200 characters in log lines.

## Success Criteria

- [ ] Starting the app and uploading a CSV produces at least `upload.started` and `csv.loaded` log lines on stdout in JSON format with all required fields.
- [ ] Running a query produces `query.received`, `node.enter`/`node.exit` for all five pipeline nodes, `sql.generated`, `sql.executed`, `chart.selected`, and `insight.generated` log lines.
- [ ] With `LANGCHAIN_TRACING_V2=true` and a valid `LANGCHAIN_API_KEY`, a completed run appears in the LangSmith UI with child spans for both Gemini LLM calls.
- [ ] Disabling LangSmith (removing `LANGCHAIN_TRACING_V2` from `.env`) does not crash the agent or emit any warnings to stdout.
- [ ] No API key values or raw secret strings appear in any log line (verified by grepping log output for the key value in integration tests).
