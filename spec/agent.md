# Agent

## Pattern

**Code-interpreter / generate-pandas-then-execute loop** (LangGraph), with a bounded self-correction retry edge. The LLM never sees the full dataset — it receives the dataframe schema + a small profile/sample and the user's question, writes pandas code, and that code is executed **locally** over the full dataframe. On execution error, the error is fed back to the LLM to regenerate (bounded). On success, the result + captured steps are summarized into a plain-language answer.

This pattern is chosen from `harness/patterns/agentic-ai.md` (code-generation-and-execution with error-driven self-correction). It replaces the baseline `transform_text` single-call node.

## State

`AgentState` (`src/graph/state.py`, `TypedDict, total=False`) — replaces the baseline transform state:

| Field | Type | Meaning |
|-------|------|---------|
| `run_id` | `str` | analyses row id (persisted) |
| `dataset_id` | `str` | which dataset this question is about |
| `question` | `str` | the user's natural-language question |
| `schema_summary` | `str` | schema + dtypes + small sample/profile (the ONLY data sent to the LLM) |
| `dataframe_path` | `str` | local path to the parsed file; the runner loads the full df from here for execution |
| `generated_code` | `str \| None` | the latest pandas code the LLM produced |
| `execution_result` | `str \| None` | repr/string of the computed result value |
| `execution_steps` | `str \| None` | captured stdout from running the code (intermediate steps) |
| `execution_error` | `str \| None` | traceback/error string if the last execution raised |
| `attempts` | `int` | how many generate→execute cycles have run |
| `max_attempts` | `int` | retry ceiling (default 3) |
| `answer` | `str \| None` | final plain-language explanation |
| `error` | `str \| None` | terminal error (e.g. retries exhausted) |
| `status` | `str` | `completed` / `failed` |

The full dataframe is **not** stored in state and never sent to the LLM. `execute_code` loads it from `dataframe_path` at execution time.

## Nodes

| Node | Function | Behavior |
|------|----------|----------|
| `generate_code` | `src/graph/nodes.py::generate_code` | Builds the prompt from `src/prompts/analyze.md` + `schema_summary` + `question` (+ on retry, the previous `generated_code` and `execution_error`). Calls Gemini via `LLMClient`. Extracts the pandas code block into `generated_code`. Increments `attempts`. Emits a structured log line. |
| `execute_code` | `src/graph/nodes.py::execute_code` | Loads the full dataframe from `dataframe_path`, runs `generated_code` in `src/execution/sandbox.py` (restricted builtins, no network/FS, timeout). On success → sets `execution_result` + `execution_steps`, clears `execution_error`. On raise → sets `execution_error`. Emits a structured log line. |
| `summarize` | `src/graph/nodes.py::summarize` | Calls Gemini once more with the question + `execution_result` + `execution_steps` to produce a concise plain-language `answer`. Sets `status="completed"`. |
| `handle_error` | `src/graph/nodes.py::handle_error` | Retries exhausted: sets `error` (last `execution_error`), `status="failed"`, and a best-effort `answer` explaining the failure. |

> Reuses the baseline `finalize`/`handle_error` shape but renames/extends them for this flow. The runner persists the final state to the `analyses` row.

## Edges & Routing

```
START
  └─▶ generate_code
        └─▶ execute_code
              └─(conditional: route_after_execute)─┐
                                                    ├─ "summarize"     (execution_error is None)
                                                    ├─ "generate_code" (error AND attempts < max_attempts)  ← self-correction retry
                                                    └─ "handle_error"  (error AND attempts >= max_attempts)
  summarize    ─▶ END
  handle_error ─▶ END
```

`route_after_execute` (`src/graph/edges.py`):
```
def route_after_execute(state):
    if not state.get("execution_error"):
        return "summarize"
    if state.get("attempts", 0) < state.get("max_attempts", 3):
        return "generate_code"   # feed the error back, regenerate
    return "handle_error"
```

## Error Handler & Finalize

- `handle_error` is the terminal failure node (retries exhausted or non-recoverable). It never surfaces a raw traceback as the user-facing answer; it produces a plain-language failure message and records the underlying `error` for the steps panel.
- `summarize` is the success finalizer. The **runner** (`src/graph/runner.py`) then persists `generated_code`, `execution_result`, `execution_steps`, `answer`, and `status` to the `analyses` row in local SQLite.

## Concurrency

Single-threaded per analysis run; the graph is invoked synchronously inside the request handler / runner. No fan-out within the graph. Multiple analyses are independent runs (separate `run_id`s). Phase 3 adds an execution timeout but does not change the graph topology.

## Graph Assembly (pseudocode — `src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import generate_code, execute_code, summarize, handle_error
from graph.edges import route_after_execute

def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("summarize", summarize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("generate_code")
    g.add_edge("generate_code", "execute_code")
    g.add_conditional_edges(
        "execute_code",
        route_after_execute,
        {
            "summarize": "summarize",
            "generate_code": "generate_code",   # retry
            "handle_error": "handle_error",
        },
    )
    g.add_edge("summarize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```

## Runner (pseudocode — `src/graph/runner.py`)

```python
def run_analysis(dataset_id: str, question: str) -> str:
    init_db()
    ds = load_dataset_meta(dataset_id)          # from datasets table
    initial = {
        "dataset_id": dataset_id,
        "question": question,
        "schema_summary": ds.schema_summary,     # schema + sample/profile only
        "dataframe_path": ds.local_path,          # full df loaded at execute time, locally
        "attempts": 0,
        "max_attempts": get_settings().max_attempts,  # default 3
        "error": None,
    }
    # create analyses row (status=pending), get run_id, set into state
    final = agentic_ai.invoke({**initial, "run_id": run_id})
    # persist generated_code, execution_result, execution_steps, answer, status to analyses row
    return run_id
```

> **Assumed:** `max_attempts` default is 3 (1 initial generate + up to 2 retries), exposed as `AGENT_MAX_ATTEMPTS`.
