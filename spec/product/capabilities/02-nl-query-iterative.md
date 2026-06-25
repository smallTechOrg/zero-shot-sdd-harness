# Capability 2: Natural Language Query (Iterative MCP Tool-Call ReAct Loop)

## Overview

The agent answers a user's natural language question by acting as an **MCP client**: it sees the attached
MCP servers and runs read-only SQL against them iteratively until it has enough information to give a
confident final answer.

This is a **ReAct loop**: the LLM reasons, picks a server and writes SQL, observes the result, and repeats
until it emits `FINAL ANSWER:`. In **Phase A** each server exposes a **generic `query` tool** (arbitrary
read-only SELECT over the server's tables); the agent addresses it with a **single-level** call. *(Phase B
adds the server's generated GET-API tools alongside the generic tool — hybrid: prefer a matching generated
tool, fall back to SQL.)*

The session's MCP pool (one in-process server per attached MCP-server entity) is built **once on the
session's first query** and reused. The agent also has **durable per-session memory** (LangGraph
`SqliteSaver`, `thread_id = session_id`): prior Q&A turns feed each new query's prompt.

## User-Facing Behaviour

1. The user types a question in a session.
2. The app acquires the session's pool (building on first use, reusing after) and runs the ReAct loop.
3. The agent runs one or more read-only DuckDB `SELECT`s (optionally joining a server's sibling tables),
   with the prior conversation as context.
4. When the LLM has enough information, it returns a plain-text final answer.
5. The session page shows the answer inline with iteration count, token usage, cost, and a collapsible
   tool-call trace.

## Agent Loop (ReAct)

```
SessionPoolManager.acquire(session_id)   ← lazy build (first query) / reuse; outside the graph
    │
    ▼
plan_action ◄─────────────────────────────────────────┐   (reads servers/columns from the manager
    │                                                  │    + the durable `conversation` memory)
    ├── (FINAL ANSWER:) → finalize → END               │
    └── (tool call JSON) → execute_action ─────────────┘
                               │  (MCP client call_tool: server → DuckDB SELECT)
                               ├── (isError) → plan_action (self-correction)
                               └── (max iterations) → handle_error
```

## LLM Protocol

### Tool call format (LLM output when it wants to act)

```json
{"tool": "<server_name>", "arguments": {"query": "SELECT ..."}}
```

A tool call is **single-level**: `tool` is the exact MCP-server name advertised in the prompt; the
`query` is read-only SQL that may JOIN any of that server's sibling tables (all views in one DuckDB
connection). Cross-server joins are not possible in one call — the agent combines those across ReAct
iterations.

### Termination format

```
FINAL ANSWER: <the complete answer in plain text>
```

## Termination Conditions

| Condition | Action |
|-----------|--------|
| LLM emits `FINAL ANSWER: ...` | Extract answer, route to `finalize` |
| DuckDB SQL error / non-SELECT SQL | Tool returns `isError=True`; append, loop back |
| Unknown server (`tool`) | Recoverable; manager returns a valid-server-list message, loop back |
| Malformed (non-JSON) tool call | Recoverable; ask to reformat, loop back |
| Iterations ≥ `max_agent_iterations` (default 10) | Route to `handle_error` |
| LLM call fails / missing Parquet / MCP session failure | Fatal — `handle_error` |

## Query Execution Rules (generic `query` via DuckDB)

- Only `SELECT`/`WITH` statements are allowed. Anything else is a recoverable `isError=True` (never run).
- The SELECT guard also rejects `;` stacking and `ATTACH`/`COPY`/`PRAGMA`/`INSTALL`/`LOAD`.
- A server's MCP server opens **one** DuckDB connection and registers a `CREATE VIEW` per table; a query
  may reference any of the server's tables and JOIN them.
- Results are capped at `DATAANALYSIS_MCP_MAX_RESULT_ROWS` (default 200) and returned as compact CSV.
- DuckDB provides native `STDDEV`/`VARIANCE`/`MEDIAN`/`QUANTILE`.

## Prompt Protocol (`plan_action`, each iteration)

```
You are a data-analysis agent operating in a ReAct loop.

Conversation so far (prior questions and answers in this session):
[1] Q: What were total sales? → A: 60.

Available tools (each tool is an MCP server; pick one and write SQL):

Tool: sales_2024  (server)
  Description: <server description>
  Tables (JOINable in one connection):
    orders(order_id BIGINT, region_id BIGINT, amount DOUBLE)
    customers(customer_id BIGINT, name VARCHAR)

SQL dialect: DuckDB. Only SELECT statements are permitted.

User question: <question>

<if history:>
Previous tool calls and results:
[1] tool: sales_2024
    arguments: {"query": "SELECT ..."}
    result: ...
</end if>

Decide your next step. Respond with EXACTLY ONE of:
1. {"tool": "<server_name>", "arguments": {"query": "SELECT ..."}}
2. FINAL ANSWER: <your complete answer here>
```

## State Fields

| Field | Type | Scope | Description |
|-------|------|-------|-------------|
| `conversation` | `list[dict]` | durable (memory) | Prior turns `{"question","answer"}`; **plain channel** — `finalize` writes the full list; restored by the checkpointer |
| `action_history` | `list[dict]` | per-query scratch | `{"tool","arguments","result","is_error"}` |
| `iteration_count` | `int` | per-query scratch | Tool calls this query |
| `llm_response` | `str` | per-query scratch | Raw last `plan_action` output |

Servers, their tables, and columns are read from the `SessionPoolManager` (by `session_id`), not stored in
state. Per-query scratch is reset via the `ainvoke` input; `conversation` accumulates as a plain channel
(do **not** make it a reducer — that double-appends on checkpoint resume).

## Persistence

| Field | Stored |
|-------|--------|
| `answer` | `query_records.answer` |
| `iteration_count` | `query_records.iteration_count` |
| `action_history` | `query_records.query_history_json` — the agent reasoning trace |
| Token counts, cost | existing columns on `query_records` |

## Out of Scope (this capability)

- Streaming intermediate results to the browser
- Chart generation (later)
- Cross-server SQL joins in a single call (combine across tool calls; within-server joins are supported)
- Hybrid consumption of generated GET-API tools by the agent — Phase B (capability 4)
- Dataset types beyond internal Parquet and external PostgreSQL (BETA)
