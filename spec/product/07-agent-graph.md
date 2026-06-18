# Agent Graph

> **Agent framework:** LangGraph (Python)
> **Agent slug:** `data-analyst`
> **Loop type:** ReAct (Reason → Act → Observe, iterative)

This file answers all eight pre-coding questions required by `spec/engineering/ai-agents.md` Section 10 before any node code is written.

---

## Pre-Coding Questions (Section 10 of ai-agents.md)

### 1. What action does the LLM generate?

A pandas operation expressed as a **method-call suffix string** — the part after `df.`, e.g.:

```
groupby('category').agg({'sales': 'sum'})
head(20)
describe()
query("age > 30")
value_counts('status')
```

The LLM is instructed (via the `plan_action.md` system prompt) to output exactly one line containing the operation tagged `ACTION:`, with no `df.` prefix and no `import` statements. The `execute_action` node extracts the `ACTION:` line and passes it to the executor. The format makes the allowlist check straightforward: split on `(` to get the method name, look it up in `SAFE_PANDAS_METHODS`.

### 2. What is the exact FINAL ANSWER string prefix?

```
FINAL ANSWER:
```

Case-insensitive match. The `after_plan_action` edge function checks `response.upper().find("FINAL ANSWER:")`. If found, the text after the prefix (trimmed) becomes `state["final_answer"]` and the edge routes to `finalize`.

The `plan_action` system prompt explicitly instructs the LLM: "When you have enough information to answer the user's question, output exactly: FINAL ANSWER: <your complete answer here>".

### 3. Recoverable vs. fatal error boundary

**Recoverable (append to `action_history`, route back to `plan_action`):**
- Any `pandas` exception during `execute_action` (e.g. `KeyError`, `ValueError`, `TypeError`, `AttributeError`)
- An action string that fails allowlist validation (unknown method or disallowed operation)
- An action string that produces an empty DataFrame or no-op result

**Fatal (set `state["error"]`, route to `handle_error`):**
- The LLM API call itself fails (network error, 4xx/5xx from Gemini, timeout)
- The dataset file is missing from disk when `setup` runs
- The `AgentState` is missing required fields (structural corruption)

Fatal errors are not retried. They persist the run as `failed` and emit an SSE error event.

### 4. Max iterations default

**10** — configured as `DATA_ANALYST_MAX_ITERATIONS` env var (default `10`) in `Settings`. When `state["iteration_count"] >= max_iterations`, the `after_plan_action` edge routes to `force_finalize` before checking for `FINAL ANSWER:`. The iteration guard is an absolute ceiling.

### 5. What does `setup` prepare and how is it cleaned up?

**Preparation:**
- Reads `state["dataset_path"]` (on-disk path of the uploaded CSV or JSON file)
- Calls `pd.read_csv(path)` or `pd.read_json(path)` based on file extension
- Stores the DataFrame in `_dataframe_store[session_id] = df` (module-level dict)
- Sets `state["dataframe_key"] = session_id`

**Cleanup:** Every terminal node (`finalize`, `force_finalize`, `handle_error`) calls `_dataframe_store.pop(session_id, None)`. A `finally` guard in `runner.py` also calls `pop` after `agent_graph.invoke()` returns so no path can leak the resource.

### 6. AgentState fields for history, iteration count, usage — and how the trace is surfaced live

All fields are in `AgentState` (see State section). The trace is surfaced live via **SSE**:
- After each `execute_action`, a `{"type": "step", "iteration": N, "action": "...", "result": "...", "is_error": false}` event is emitted.
- After `finalize` or `force_finalize`, a `{"type": "answer", "text": "...", "tokens_input": N, "tokens_output": N, "estimated_cost_usd": N}` event is emitted.
- After `handle_error`, a `{"type": "error", "message": "..."}` event is emitted.
- The UI renders each step event in a collapsible "Reasoning steps" panel and the final answer in the chat thread.
- `action_history` is also persisted to `RunRow` as JSON text at run end for audit and replay.

### 7. Action-safety boundary

`tools/pandas_executor.py` is the sole execution surface:

1. **Method extraction:** Regex extracts the leading method name before `(`. Never `eval` or `exec`.
2. **Allowlist check:** Method must be in `SAFE_PANDAS_METHODS` (frozenset of read-only pandas methods). Unknown methods raise `ValueError("Action not permitted: <method>")`.
3. **Dispatch:** `getattr(df, method_name)(*parsed_args, **parsed_kwargs)` — resolved on the real DataFrame object, not executed as arbitrary Python.
4. **Result serialisation:** DataFrame → `result.head(20).to_dict(orient="records")`; Series → `result.head(20).to_dict()`; scalar → `str(result)`.

Never permitted: `to_sql`, `to_csv`, `to_parquet`, `to_excel`, `drop`, `insert`, `update`, `delete`, `exec`, `eval`, `apply` with user-supplied callables, import statements, multi-statement strings. Every action string is treated as untrusted input.

### 8. What does `force_finalize` synthesise when iterations are exhausted?

`force_finalize` makes one final LLM call with `prompts/force_finalize.md`. The prompt provides the full `action_history` and instructs the LLM to synthesise the best answer from what was discovered, noting what could not be determined. The output must start with a concrete answer — never a bare "I couldn't answer." If the LLM call fails, a static fallback is used: "Analysis incomplete after {N} iterations. Findings so far: [formatted action_history summary]." The `RunRow` is persisted with `status=completed` and `error_message=iteration_limit_reached`.

---

---

## State

```python
from typing import TypedDict

class AgentState(TypedDict, total=False):
    # Identity
    run_id: str          # UUID for this question-answer run; foreign key to RunRow
    session_id: str      # browser session UUID; key into _dataframe_store

    # Dataset
    dataset_path: str    # absolute path to the uploaded file on disk
    dataframe_key: str   # equals session_id — key used to retrieve df from _dataframe_store

    # Question
    user_question: str   # the user's natural-language question

    # ReAct loop
    action_history: list[dict]
    # each entry: {"action": str, "result": str, "is_error": bool}
    # - action: the pandas operation string the LLM generated
    # - result: serialised output (JSON rows, scalar, or error message)
    # - is_error: True if execution or validation failed

    iteration_count: int       # number of plan_action → execute_action cycles completed
    llm_response: str          # raw last LLM output — router checks it for FINAL ANSWER:

    # Output
    final_answer: str | None   # set by finalize or force_finalize

    # Usage accounting — accumulated across all LLM calls; persisted on RunRow
    tokens_input: int
    tokens_output: int
    estimated_cost_usd: float | None

    # Error — set by any node on fatal failure; routes to handle_error
    error: str | None
```

All fields use `total=False` (optional) so nodes can return partial state updates. LangGraph merges partial updates into the full state object.

---

## Nodes

### `setup`

**Reads from state:** `session_id`, `dataset_path`

**Writes to state:** `dataframe_key`, `action_history` (initialised to `[]`), `iteration_count` (set to `0`), `tokens_input` (set to `0`), `tokens_output` (set to `0`), `estimated_cost_usd` (set to `0.0`), `error` (set on failure)

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Filesystem | Read uploaded file at `dataset_path` | Fatal — set `error`, route to `handle_error` |
| pandas | `pd.read_csv` or `pd.read_json` | Fatal — set `error` with parse message, route to `handle_error` |
| Module-level `_dataframe_store` | `_dataframe_store[session_id] = df` | Cannot fail (in-memory dict) |

**Behaviour:** Validates that `dataset_path` exists on disk. Determines file type from extension (`.csv` → `pd.read_csv`, `.json` → `pd.read_json`). Loads the file into a DataFrame. Stores it in `_dataframe_store` keyed by `session_id` (same value as `dataframe_key`). Initialises all loop counters to zero. On any I/O or parse error, sets `state["error"]` with a human-readable message — the edge routes to `handle_error`.

---

### `plan_action`

**Reads from state:** `session_id`, `run_id`, `user_question`, `action_history`, `iteration_count`, `dataframe_key`, `tokens_input`, `tokens_output`, `estimated_cost_usd`

**Writes to state:** `llm_response`, `tokens_input`, `tokens_output`, `estimated_cost_usd`, `error` (set on LLM API failure)

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini API | `model.generate_content(prompt)` | Fatal — set `error`, route to `handle_error` |

**Behaviour:** Retrieves the DataFrame from `_dataframe_store[session_id]` to extract schema (column names, dtypes, `df.head(3).to_dict(orient="records")`). Builds the system prompt from `prompts/plan_action.md`, injecting: user question, dataset schema, `action_history` (formatted as numbered steps with results), and iteration count. Calls Gemini. Accumulates token usage. Sets `state["llm_response"]` to the raw text. On LLM API error, sets `state["error"]` and returns. The `after_plan_action` edge reads `llm_response` to decide routing.

---

### `execute_action`

**Reads from state:** `session_id`, `run_id`, `dataframe_key`, `llm_response`, `action_history`, `iteration_count`

**Writes to state:** `action_history` (appended), `iteration_count` (incremented)

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| `tools/pandas_executor` | `validate_and_execute(action_str, df)` | Recoverable — append error entry to history, loop back |

**Behaviour:** Parses the `ACTION:` line from `llm_response`. Retrieves the DataFrame from `_dataframe_store[dataframe_key]`. Calls `validate_and_execute(action_str, df)` from `tools/pandas_executor.py`. Appends `{"action": action_str, "result": result_str, "is_error": is_error}` to `action_history`. Increments `iteration_count`. Emits an SSE step event. All errors — allowlist violations and pandas exceptions alike — are caught and recorded as `is_error: True` entries. The node never routes to `handle_error`; all errors are recoverable.

---

### `finalize`

**Reads from state:** `run_id`, `session_id`, `llm_response`, `action_history`, `tokens_input`, `tokens_output`, `estimated_cost_usd`

**Writes to state:** `final_answer`

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite (via SQLAlchemy) | Update `RunRow`: status=`completed`, final_answer, action_history JSON, usage fields, completed_at | Log warning; do not re-raise |
| `_dataframe_store` | `pop(session_id, None)` | Cannot fail |

**Behaviour:** Strips the `FINAL ANSWER:` prefix from `llm_response` to get the final answer text. Sets `state["final_answer"]`. Updates the `RunRow` in SQLite with all final fields. Pops the DataFrame from `_dataframe_store`. Emits a final SSE `answer` event. DB write errors are logged as warnings but do not re-raise — the answer has been computed and streamed.

---

### `force_finalize`

**Reads from state:** `run_id`, `session_id`, `user_question`, `action_history`, `tokens_input`, `tokens_output`, `estimated_cost_usd`

**Writes to state:** `final_answer`, `tokens_input`, `tokens_output`, `estimated_cost_usd`

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini API | One final synthesis call using `prompts/force_finalize.md` | Fall back to static summary of `action_history` without LLM |
| SQLite | Update `RunRow`: status=`completed`, error_message=`iteration_limit_reached`, final_answer, usage | Log warning; do not re-raise |
| `_dataframe_store` | `pop(session_id, None)` | Cannot fail |

**Behaviour:** Reached when `iteration_count >= max_iterations` before `FINAL ANSWER:` is emitted. Makes one final LLM call with the full `action_history` and the synthesis prompt. If the LLM call fails, falls back to a static text: "Analysis incomplete after {N} iterations. Findings so far: [formatted action_history summary]." Sets `state["final_answer"]`. Persists to DB with `error_message="iteration_limit_reached"`. Releases DataFrame. Emits final SSE `answer` event. Never produces a bare "I couldn't answer."

---

### `handle_error`

**Reads from state:** `run_id`, `session_id`, `error`, `action_history`, `tokens_input`, `tokens_output`, `estimated_cost_usd`

**Writes to state:** nothing (terminal node)

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Update `RunRow`: status=`failed`, error_message, action_history JSON, usage fields, completed_at | Log and continue |
| `_dataframe_store` | `pop(session_id, None)` | Cannot fail |

**Behaviour:** Logs the fatal error at `ERROR` level with full context. Updates the `RunRow` to `failed` in SQLite. Releases the DataFrame. Emits a final SSE `error` event. Terminates the graph. Never retries.

---

## Edge Topology

ASCII diagram of the full ReAct loop with iteration guard:

```
START
  │
  ▼
┌─────────────────────┐
│        setup        │──(error)─────────────────────────────────────────────────────┐
└─────────────────────┘                                                               │
  │ (success)                                                                         │
  ▼                                                                                   │
┌─────────────────────┐                                                               │
│    plan_action      │──(LLM API error)────────────────────────────────────────────┤
└─────────────────────┘                                                               │
  │                                                                                   │
  ├──(iteration_count >= MAX_AGENT_ITERATIONS) ─────────────────────────────────┐    │
  │                                                                              │    │
  ├──("FINAL ANSWER:" in llm_response) ────────────────────────────────────┐    │    │
  │                                                                         │    │    │
  │ (action string — normal ReAct iteration)                                │    │    │
  ▼                                                                         │    │    │
┌─────────────────────┐                                                     │    │    │
│   execute_action    │  ← all pandas errors are recoverable:               │    │    │
│                     │    appended to action_history as is_error=True      │    │    │
└─────────────────────┘                                                     │    │    │
  │ (always unconditional — loops back)                                     │    │    │
  └────────────────────────────────────────► plan_action (observe loop)    │    │    │
                                                                            │    │    │
                                                                            ▼    │    │
                                                                   ┌─────────────┤    │
                                                                   │  finalize   │    │
                                                                   └─────────────┘    │
                                                                            │         │
                                                                            ▼         │
                                                                           END        │
                                                                                      │
                                                                   ┌──────────────────┤
                                                                   │ force_finalize   │◄─(iter limit)
                                                                   └──────────────────┘
                                                                            │
                                                                            ▼
                                                                           END

                                                                   ┌──────────────────┐
                                                                   │  handle_error    │◄─(fatal errors)
                                                                   └──────────────────┘
                                                                            │
                                                                            ▼
                                                                           END

Note: The iteration guard in after_plan_action is checked BEFORE the FINAL ANSWER check,
      enforcing the hard iteration ceiling even if the LLM emits FINAL ANSWER: late.
```

---

## Graph Assembly (`graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from data_analyst.graph.state import AgentState
from data_analyst.graph.nodes import (
    setup, plan_action, execute_action,
    finalize, force_finalize, handle_error,
)
from data_analyst.graph.edges import after_setup, after_plan_action

def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("setup", setup)
    g.add_node("plan_action", plan_action)
    g.add_node("execute_action", execute_action)
    g.add_node("finalize", finalize)
    g.add_node("force_finalize", force_finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("setup")

    g.add_conditional_edges(
        "setup",
        after_setup,
        {"plan_action": "plan_action", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "plan_action",
        after_plan_action,
        {
            "execute_action": "execute_action",
            "finalize": "finalize",
            "force_finalize": "force_finalize",
            "handle_error": "handle_error",
        },
    )
    # observe → reason: unconditional, always loops back
    g.add_edge("execute_action", "plan_action")

    g.add_edge("finalize", END)
    g.add_edge("force_finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()

agent_graph = _build_graph()
```

## Edge Functions (`graph/edges.py`)

```python
from data_analyst.graph.state import AgentState
from data_analyst.config.settings import get_settings

def after_setup(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "plan_action"

def after_plan_action(state: AgentState) -> str:
    settings = get_settings()
    max_iter = settings.max_iterations  # DATA_ANALYST_MAX_ITERATIONS, default 10

    # Iteration guard fires first — absolute ceiling
    if state.get("iteration_count", 0) >= max_iter:
        return "force_finalize"

    # Fatal LLM error
    if state.get("error"):
        return "handle_error"

    # Termination signal
    response = (state.get("llm_response") or "").strip()
    if "FINAL ANSWER:" in response.upper():
        return "finalize"

    # Normal action — continue loop
    return "execute_action"
```

---

## Concurrency Model

- **One agent run per HTTP request.** FastAPI handles each `POST /api/chat/ask` request in a thread from the default thread pool. LangGraph runs synchronously within that thread. The SSE generator yields events as nodes complete.
- **Session isolation.** Each session's DataFrame lives in its own slot in `_dataframe_store`. Concurrent sessions do not share mutable state.
- **No LangGraph checkpointing** in v0.1 — runs are short (≤ 10 iterations) and the full state is persisted to SQLite at completion. If the server restarts mid-run, the run stays in `running` status and the user must resubmit the question.
- **No parallel nodes** — all nodes run sequentially within a single request.
- **Thread safety of `_dataframe_store`:** The module-level dict is accessed from one thread per session. Safe for a single Uvicorn worker. If multiple workers are added in a future phase, replace with a process-safe store (e.g. Redis).
