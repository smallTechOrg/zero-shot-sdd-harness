# Capability 2: Iterative SQL-Driven Natural Language Query

## Overview

The agent answers a user's natural language question by iteratively generating and executing SQL queries against the uploaded CSV data until it has enough information to provide a confident final answer.

This replaces the original "sample + single LLM call" approach with a **ReAct loop**: the LLM reasons, acts (generates SQL), observes the result, and repeats until it can conclude.

## User-Facing Behaviour

1. User types a natural language question about an uploaded dataset.
2. The agent runs one or more SQL queries against the full dataset (not just a sample).
3. When the LLM determines it has enough information, it returns a plain-text final answer.
4. The answer page shows: the answer, how many SQL iterations were run, total token usage, and estimated cost.

## Agent Loop (ReAct)

```
load_data
    │
    ▼
plan_query ◄────────────────────────────┐
    │                                   │
    ▼                                   │
[LLM output has SQL?] ──yes──► execute_query ──► [max iterations?]
    │ no (FINAL ANSWER)                              │ no ──────────┘
    ▼                                               │ yes
finalize                                            ▼
    │                                          handle_error (timeout)
    ▼
  END
```

## Termination Conditions

| Condition | Action |
|-----------|--------|
| LLM emits `FINAL ANSWER: ...` | Extract answer text, route to `finalize` |
| Iteration count ≥ `max_agent_iterations` (default 10) | Route to `handle_error` with "max iterations exceeded" |
| Any node raises an exception | Route to `handle_error` |

## SQL Execution Rules

- Only `SELECT` statements are allowed. Non-SELECT SQL is rejected as an error.
- The table is always named `data`.
- Results are capped at 200 rows to keep LLM context bounded.
- Numeric results are formatted to 4 significant figures.
- The full CSV is loaded into an in-memory SQLite database at the start of each pipeline run.

## Prompt Protocol

### `plan_query` prompt (each iteration)

```
You are a data analyst. You have access to a SQL executor connected to the following dataset:

Table: data
Columns: <column_names>

User question: <question>

<if iteration > 0:>
Previous queries and results:
[1] SQL: SELECT ...
    Result: ...

[2] SQL: SELECT ...
    Result: ...
</end if>

Based on the above, decide your next step:
- If you need more data: respond with a single SQL SELECT query and nothing else.
- If you have enough information to answer the user's question: respond with exactly:
  FINAL ANSWER: <your complete answer here>

Do not include markdown, backticks, or explanations when writing SQL.
```

## State Fields (additions to existing AgentState)

| Field | Type | Description |
|-------|------|-------------|
| `query_history` | `list[dict]` | Each entry: `{"sql": str, "result": str}` |
| `iteration_count` | `int` | Number of SQL queries executed so far |
| `llm_response` | `str` | Raw LLM output from last `plan_query` call |

## Persistence

| Field | Stored in DB |
|-------|-------------|
| `answer` | Yes (`query_records.answer`) |
| `iteration_count` | Yes (`query_records.iteration_count`) |
| `query_history` | No (transient pipeline state only) |
| Token counts, cost | Yes (existing columns) |

## Out of Scope (this capability)

- Streaming intermediate results to the browser
- User-visible query history / step-by-step trace in the UI
- Chart generation from SQL results (see Capability 4)
