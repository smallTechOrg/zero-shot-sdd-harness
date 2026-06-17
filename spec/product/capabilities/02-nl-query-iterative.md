# Capability 2: Natural Language Query (Iterative Tool-Call ReAct Loop)

## Overview

The agent answers a user's natural language question by iteratively invoking tool capabilities loaded from the database until it has enough information to provide a confident final answer.

This is a **ReAct loop**: the LLM reasons, selects a tool capability to invoke, observes the result, and repeats until it emits `FINAL ANSWER:`. Tool capabilities are not hardcoded — they are loaded from SQLite at runtime, making the loop reusable across different data source types.

## User-Facing Behaviour

1. User types a natural language question in a session.
2. The agent loads the tool registry for the session's DataSource.
3. The agent runs one or more tool capability invocations (e.g., SQL queries).
4. When the LLM determines it has enough information, it returns a plain-text final answer.
5. The session page shows the answer inline with: iteration count, token usage, cost estimate, and collapsible SQL trace.

## Agent Loop (ReAct)

```
load_data (load Tool registry from DB + load CSV into in-memory SQLite)
    │
    ▼
plan_action ◄─────────────────────────────────────────┐
    │                                                  │
    ├── (FINAL ANSWER:) → finalize → END               │
    │                                                  │
    └── (tool call JSON) → execute_action ─────────────┘
                               │
                               └── (error) → plan_action (self-correction)
                               └── (max iterations) → handle_error
```

## LLM Protocol

### Tool call format (LLM output when it wants to act)

```json
{"capability": "run_query", "parameters": {"query": "SELECT ..."}}
```

### Termination format (LLM output when it's done)

```
FINAL ANSWER: <the complete answer in plain text>
```

## Termination Conditions

| Condition | Action |
|-----------|--------|
| LLM emits `FINAL ANSWER: ...` | Extract answer, route to `finalize` |
| SQL error | Append error to history as `is_error: True`, loop back to `plan_action` |
| Iteration count ≥ `max_agent_iterations` (default 10) | Route to `handle_error` ("max iterations exceeded") |
| Unknown capability name | Fatal — route to `handle_error` |
| Non-SELECT SQL | Fatal — route to `handle_error` |
| LLM call fails | Fatal — route to `handle_error` |

## Tool Call Execution Rules (csv_query / run_query)

- Only `SELECT` statements are allowed. Non-SELECT SQL is a fatal error.
- The table is always named `data`.
- Results are capped at 200 rows to keep LLM context bounded.
- Numeric results are formatted to 4 significant figures.
- The full CSV is loaded into an in-memory SQLite database at the start of each pipeline run.

## Prompt Protocol

### `plan_action` prompt (each iteration)

```
You are a data analyst. You have access to the following tools:

Tool: csv_query
  Capability: run_query
  Description: Execute a SQL SELECT query against the dataset. The table is always named 'data'.
  Parameters: {"query": {"type": "string"}}

Dataset schema:
Table: data
Columns: <column_names>

User question: <question>

<if iteration > 0:>
Previous tool calls and results:
[1] capability: run_query
    parameters: {"query": "SELECT ..."}
    result: ...

[2] capability: run_query
    parameters: {"query": "SELECT ..."}
    result: Error: misuse of aggregate function MIN()
    → This call failed. Please correct it.
</end if>

Based on the above, decide your next step:
- If you need more data: respond with a JSON tool call (no markdown, no backticks).
- If you have enough information: respond with exactly:
  FINAL ANSWER: <your complete answer here>
```

## State Fields

| Field | Type | Description |
|-------|------|-------------|
| `tools` | `list[dict]` | Loaded from DB: `[{"name", "type", "capabilities": [{"name", "description", "parameter_schema"}]}]` |
| `action_history` | `list[dict]` | Each entry: `{"capability": str, "parameters": dict, "result": str, "is_error": bool}` |
| `iteration_count` | `int` | Number of tool calls executed so far |
| `llm_response` | `str` | Raw LLM output from last `plan_action` call |

## Persistence

| Field | Stored in DB |
|-------|-------------|
| `answer` | Yes (`query_records.answer`) |
| `iteration_count` | Yes (`query_records.iteration_count`) |
| `action_history` | Yes (`query_records.query_history_json`) — displayed as agent reasoning trace in UI |
| Token counts, cost | Yes (existing columns on `query_records`) |

## Out of Scope (this capability)

- Streaming intermediate results to the browser (deferred)
- Chart generation from tool results (Capability 5)
- Non-CSV data source types (future tool executors)
