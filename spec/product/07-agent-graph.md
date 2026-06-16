# Agent Graph

## State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    query_record_id: str
    dataset_id: str

    # Input
    question: str
    csv_path: str

    # Schema (populated by load_data)
    column_names: list[str]
    row_count: int

    # ReAct loop state
    query_history: list[dict]   # [{"sql": str, "result": str}, ...]
    iteration_count: int        # number of SQL queries executed
    llm_response: str           # raw LLM output from plan_query

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

**Reads from state:** `csv_path`, `dataset_id`

**Writes to state:** `column_names`, `row_count`, `query_history` (initialized to `[]`), `iteration_count` (initialized to `0`)

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Read CSV with pandas | Fatal — set `error`, route to `handle_error` |

**Behaviour:** Reads the CSV file using pandas. Extracts column names and row count. Initialises `query_history = []` and `iteration_count = 0` in state. The full DataFrame is loaded into an in-memory SQLite database (table name: `data`) inside a module-level cache keyed by `run_id`. This cache is used by `execute_query` and cleaned up in `finalize`/`handle_error`.

---

### `plan_query`

**Reads from state:** `question`, `column_names`, `query_history`, `iteration_count`, `api_request_count`, token fields

**Writes to state:** `llm_response`, `answer` (if FINAL ANSWER detected), `input_tokens`, `output_tokens`, `total_tokens`, `estimated_cost_usd`, `api_request_count`

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| OpenRouter (or stub) | Chat completion | Fatal — set `error`, route to `handle_error` |

**Behaviour:** Builds a prompt containing the table schema, the user's question, and the full `query_history` so far. Sends to LLM. Accumulates token counts into state.

If the response starts with `FINAL ANSWER:`, strips the prefix and sets `state["answer"]`. The conditional router then routes to `finalize`.

If the response is a SQL query, sets `state["llm_response"]` and routes to `execute_query`.

Stub tag injected into prompt: `<node:plan_query>`

---

### `execute_query`

**Reads from state:** `run_id`, `llm_response`, `query_history`, `iteration_count`

**Writes to state:** `query_history` (appended), `iteration_count` (incremented)

**External calls:** None (in-memory SQLite only)

**Behaviour:**
1. Validates that `llm_response` is a `SELECT` statement. Non-SELECT SQL is a fatal error.
2. Executes the SQL against the in-memory SQLite DB (loaded in `load_data`).
3. Formats results as a compact CSV string, capped at 200 rows.
4. Appends `{"sql": ..., "result": ...}` to `query_history`.
5. Increments `iteration_count`.

---

### `finalize`

**Reads from state:** `run_id`, `query_record_id`, `answer`, `iteration_count`, token fields

**Writes to state:** _(none — side-effects only)_

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Update QueryRecord: answer, iteration_count, token fields, status=completed | Fatal — set `error` |
| SQLite | Update AgentRun status=completed | Fatal — set `error` |

**Behaviour:** Persists the final answer and all usage stats to the database. Removes the in-memory SQLite DB from the module-level cache. Updates AgentRun to `completed`.

---

### `handle_error`

**Reads from state:** `error`, `run_id`, `query_record_id`

**Writes to state:** _(none — side-effects only)_

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Update QueryRecord status=failed, error_message | Best-effort |
| SQLite | Update AgentRun status=failed, error_message | Best-effort |

**Behaviour:** Persists failure state to the database. Removes the in-memory SQLite DB from the module-level cache (best-effort). Logs error with run_id context. Terminates graph.

---

## Edge Topology

```
START
  │
  ▼
load_data ──(error)──────────────────────────► handle_error ──► END
  │
  ▼
plan_query ◄──────────────────────────────────┐
  │                                           │
  ├──(error)──► handle_error                  │
  │                                           │
  ├──(FINAL ANSWER)──► finalize ──► END       │
  │                                           │
  └──(SQL query)──► execute_query ────────────┘
                        │
                        ├──(error)──► handle_error
                        │
                        └──(iteration_count >= max)──► handle_error
```

---

## Graph Assembly

```python
graph = StateGraph(AgentState)

graph.add_node("load_data", load_data)
graph.add_node("plan_query", plan_query)
graph.add_node("execute_query", execute_query)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("load_data")

graph.add_conditional_edges("load_data", route_after_load,
    {"plan_query": "plan_query", "handle_error": "handle_error"})

graph.add_conditional_edges("plan_query", route_after_plan,
    {"execute_query": "execute_query",
     "finalize": "finalize",
     "handle_error": "handle_error"})

graph.add_conditional_edges("execute_query", route_after_execute,
    {"plan_query": "plan_query",
     "handle_error": "handle_error"})

graph.add_conditional_edges("finalize", route_after_finalize,
    {"end": END, "handle_error": "handle_error"})

graph.add_edge("handle_error", END)

compiled_graph = graph.compile()
```

---

## Concurrency Model

- One query runs at a time per user request (HTTP request per query, synchronous).
- The in-memory SQLite cache (`_db_cache: dict[str, sqlite3.Connection]`) is process-local and not shared across requests. Each `run_id` gets its own connection.
- No checkpointing in v0.1.
