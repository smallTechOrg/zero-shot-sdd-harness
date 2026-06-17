# Agent Graph

> **Mandatory pre-coding checklist** — answer all six questions before writing any node code.
> If any are missing, raise a blocker. (See `spec/engineering/ai-agents.md` Section 10.)
>
> 1. **Action type:** What does the LLM generate? → A tool capability invocation: `{"capability": "run_query", "parameters": {"query": "<SQL>"}}`
> 2. **Termination signal:** How does the LLM say it's done? → Response starts with `FINAL ANSWER:`
> 3. **Recoverable vs fatal errors:** SQL execution errors → feed back to LLM. Non-SELECT SQL, unknown capability, LLM failures → fatal.
> 4. **Max iterations default:** `10` (configurable via `DATAANALYSIS_MAX_AGENT_ITERATIONS`)
> 5. **In-session data store:** In-memory SQLite connection per `run_id`, stored in module-level `_db_cache` dict, cleaned up by both `finalize` and `handle_error`.
> 6. **State fields for history:** `action_history: list[dict]`, `iteration_count: int`, `llm_response: str`, `tools: list[dict]` (loaded from DB at run start)

---

## State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    query_record_id: str
    session_id: str
    data_source_id: str

    # Input
    question: str
    csv_path: str           # for csv_query tools

    # Tool registry (loaded from DB by load_data)
    tools: list[dict]       # [{"name": str, "type": str, "capabilities": [{"name": str, "description": str, "parameter_schema": dict}]}]

    # Schema (populated by load_data for csv tools)
    column_names: list[str]
    row_count: int

    # ReAct loop state
    action_history: list[dict]   # [{"capability": str, "parameters": dict, "result": str, "is_error": bool}]
    iteration_count: int
    llm_response: str            # raw LLM output from plan_action

    # Final output
    answer: str

    # Usage tracking
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    api_request_count: int

    # Control
    error: str | None
```

---

## Nodes

### `load_data`

**Reads from state:** `data_source_id`, `run_id`, `csv_path`, `session_id`

**Writes to state:** `column_names`, `row_count`, `action_history` (initialized to `[]`), `iteration_count` (initialized to `0`), `tools` (loaded from DB)

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite (DB) | Load Tool + ToolCapability records for this DataSource | Fatal |
| Local filesystem | Read CSV with pandas | Fatal |

**Behaviour:** Loads the Tool registry for the DataSource from the DB (`tools` list with nested capabilities). For `csv_query` tools, reads the CSV into an in-memory SQLite database (table: `data`) and stores the connection in `_db_cache[run_id]`. Extracts `column_names` and `row_count` from the DataFrame. Initialises `action_history = []` and `iteration_count = 0`.

---

### `plan_action`

**Reads from state:** `question`, `column_names`, `tools`, `action_history`, `iteration_count`, token fields

**Writes to state:** `llm_response`, `answer` (if FINAL ANSWER detected), token fields

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| OpenRouter (or stub) | Chat completion | Fatal |

**Behaviour:** Builds a prompt containing:
- Available tools and their capabilities (from `state["tools"]`)
- Table schema (column names and types)
- The user's question
- The full `action_history` so far (including errors)

Sends to LLM. Accumulates token counts.

If the response starts with `FINAL ANSWER:`, strips the prefix, sets `state["answer"]`, routes to `finalize`.
If the response is a JSON tool call, sets `state["llm_response"]` and routes to `execute_action`.

Stub tag injected into prompt: `<node:plan_action>`

---

### `execute_action`

**Reads from state:** `run_id`, `llm_response`, `action_history`, `iteration_count`, `tools`

**Writes to state:** `action_history` (appended), `iteration_count` (incremented)

**External calls:** None (dispatches to in-process tool executors only)

**Behaviour:**
1. Parses `llm_response` as JSON: `{"capability": str, "parameters": dict}`.
2. Looks up the named capability across all loaded tools; fails fatally if not found.
3. Dispatches to the appropriate executor by tool type:
   - `csv_query` / `run_query`: validates SELECT-only, executes against `_db_cache[run_id]`, formats results as compact CSV (max 200 rows)
   - (future) `api_call`, `graphql_query`, `shell_exec`: separate executor branches
4. On SQL/execution error: appends `{..., "is_error": True}` to `action_history`, increments `iteration_count`, routes back to `plan_action` (self-correction).
5. Checks `iteration_count >= max_iterations` → routes to `handle_error` if true.

---

### `finalize`

**Reads from state:** `run_id`, `query_record_id`, `answer`, `iteration_count`, `action_history`, token fields

**Writes to state:** _(none — side-effects only)_

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Update QueryRecord: answer, iteration_count, action_history JSON, token fields, status=completed | Fatal |
| SQLite | Update AgentRun status=completed | Fatal |

**Behaviour:** Persists the final answer and usage stats to the database. Removes the in-memory SQLite DB from `_db_cache`. Updates AgentRun to `completed`.

---

### `handle_error`

**Reads from state:** `error`, `run_id`, `query_record_id`

**Writes to state:** _(none — side-effects only)_

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Update QueryRecord status=failed, error_message | Best-effort |
| SQLite | Update AgentRun status=failed, error_message | Best-effort |

**Behaviour:** Persists failure state. Removes in-memory SQLite DB from `_db_cache` (best-effort). Logs error with run_id. Terminates graph.

---

## Edge Topology

```
START
  │
  ▼
load_data ──(error)──────────────────────────► handle_error ──► END
  │
  ▼
plan_action ◄─────────────────────────────────┐
  │                                           │
  ├──(error)──► handle_error                  │
  │                                           │
  ├──(FINAL ANSWER)──► finalize ──► END       │
  │                                           │
  └──(tool call)──► execute_action ───────────┘
                        │
                        ├──(fatal error)──► handle_error
                        │
                        └──(iteration_count >= max)──► handle_error
```

---

## Graph Assembly

```python
graph = StateGraph(AgentState)

graph.add_node("load_data", load_data)
graph.add_node("plan_action", plan_action)
graph.add_node("execute_action", execute_action)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("load_data")

graph.add_conditional_edges("load_data", route_after_load,
    {"plan_action": "plan_action", "handle_error": "handle_error"})

graph.add_conditional_edges("plan_action", route_after_plan,
    {"execute_action": "execute_action",
     "finalize": "finalize",
     "handle_error": "handle_error"})

graph.add_conditional_edges("execute_action", route_after_execute,
    {"plan_action": "plan_action",
     "handle_error": "handle_error"})

graph.add_conditional_edges("finalize", route_after_finalize,
    {"end": END, "handle_error": "handle_error"})

graph.add_edge("handle_error", END)

compiled_graph = graph.compile()
```

---

## Tool Prompt Format

The `plan_action` prompt describes the available tools to the LLM. For each capability:

```
Available tools:

Tool: csv_query
  Capability: run_query
  Description: Execute a SQL SELECT query against the dataset. The table is always named 'data'.
  Parameters: {"query": {"type": "string", "description": "A valid SQL SELECT statement."}}

To use a tool, respond with a JSON object:
{"capability": "run_query", "parameters": {"query": "SELECT ..."}}

To signal that you have enough information to answer, respond with:
FINAL ANSWER: <your complete answer here>
```

---

## Concurrency Model

- One query runs at a time per user request (HTTP request per query, synchronous).
- The in-memory SQLite cache (`_db_cache: dict[str, sqlite3.Connection]`) is process-local. Each `run_id` gets its own connection.
- No checkpointing in v0.1.
