# Agent

> Required: this project uses LangGraph. This file specifies the full ReAct `StateGraph`. It REWRITES the skeleton's `transform_text` graph in place (`src/graph/state.py`, `nodes.py`, `edges.py`, `agent.py`, `runner.py`) and ADDS `sandbox.py`, `preflight.py`, `suggestions.py`, `describe.py`, `compress.py`, `derived.py`, `memory.py`.

---

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Single-agent loop** | One LLM drives a deterministic tool-call loop. No branches, no handoffs. |
| **Graph (LangGraph)** | Multi-step pipeline with conditional edges, checkpointing, or parallel nodes. |
| **Multi-agent** | Specialised sub-agents with distinct roles; orchestrator routes between them. |
| **Supervisor** | One supervisor LLM dispatches to worker agents based on task type. |
| **Human-in-the-loop** | Execution pauses at defined checkpoints for user review or approval. |

**Chosen:** **Graph (LangGraph) ReAct loop.** A single LLM reasons and emits one pandas action per turn; the agent executes it and feeds the result back, iterating with conditional edges (self-correct on error, force-finalize on max-iter / consecutive errors). The conditional edges, the iteration/error counters, and the live DB-write-per-step rule make this a graph, not a flat loop.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `plan_action` (per-iteration reasoning) | Gemini | `gemini-3.1-flash-lite` (→ `gemini-2.5-flash` on 404) | Cheapest fast model that follows the ReAct format; called every iteration, so latency/cost dominate. |
| `force_finalize` (synthesis) | Gemini | same | One synthesis call; quality-over-cost but the same model is sufficient. |
| `check_clarification` (C26), `select_datasets` (C19), `generate_suggestions`, `generate_dataset_notes` (C30), `extract_facts` (C31) | Gemini | same | Single-shot helpers outside the graph; same model via `LLMClient`. |

All calls go through `LLMClient.call_model(prompt, *, system=None)` — **never the provider SDK directly**. Provider is auto-detected (Gemini key → gemini; else OpenRouter; else stub). Model override via `AGENT_LLM_MODEL`.

**Fallback behaviour:** No key → stub provider auto-engages (yellow UI banner). A Gemini API/network error inside `execute_action`'s recoverable path or a `plan_action` transient error routes back to `plan_action` to retry the reasoning; a fatal load/setup error routes to `handle_error` (run `failed`, clear message). `force_finalize` falls back to a static best-effort message if its single LLM call fails. This is production resilience — tests call the real Gemini with keys from `.env`.

**Prompt strategy:** System/user split. `plan_action` prompt is assembled from question + `action_history` (Action/Result/Error transcript) + `conversation_history` + `dataset_context` + persistent memory + column schema, with an injected `<node:plan>` tag. The model must reply either `FINAL ANSWER: <markdown>` or a bare pandas expression to execute. Helpers (`select`, `clarify`, `suggest`, `describe`, `compress`) request structured output (JSON arrays / a single question / plain text) and carry their own `<node:...>` tags where the stub must branch.

---

## Tools & Tool Calling

The agent does not use the LLM-native tool-calling API; its single "tool" is **eval of a pandas expression** the model emits as text, executed in a fixed sandbox namespace. The sandbox functions:

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| pandas eval (`execute_action`) | Eval/exec the model's expression against the loaded DataFrame(s) | expression string | stringified result (+ captured Plotly figure JSON) | none on the DataFrame in place (read-mostly); captures charts |
| `save_dataset(df, name, desc)` | Materialise a DataFrame as a registered DERIVED dataset | DataFrame, name, description | confirmation string | writes `uploads/{id}.csv` + `.parquet`; inserts a `datasets` row (origin=derived) with `derivation_code` + parents + producing run (C25) |

**Sandbox namespace** (provided to `execute_action`): `df` (first DataFrame), `df1`/`df2`/… (per-dataset, ordered by `dataset_ids`), a `<filename_stem>` alias per dataset, and the libraries `pd, np, px, go, plt, sns, scipy, stats, sklearn, sm`, plus `save_dataset`. No filesystem/network builtins beyond these are exposed.

**Tool selection strategy:** The LLM chooses the next pandas expression each iteration (free-form reasoning). The agent does not route between multiple tools — it either executes the expression or, on `FINAL ANSWER:`, finalizes.

**Tool failure handling:** An exception in `execute_action` is caught, recorded as `{action, result, is_error: true}` in `action_history`, and the graph routes **back to `plan_action`** so the model self-corrects (recoverable). Three consecutive errors → `force_finalize`. A fatal error (e.g. DataFrame load failure in `setup`) → `handle_error`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                          # set at initialisation (query_runs.id)

    # Input
    dataset_ids: list[str]               # resolved datasets to load (explicit or C19 selector)
    dataset_context: str | None          # concatenated dataset notes injected into the prompt
    session_id: str | None               # set when the run belongs to a conversation session
    question: str                        # the user's plain-English question
    conversation_history: list[dict]     # prior turns {question, answer} for the session

    # Pipeline data (populated progressively by nodes)
    action_history: list[dict]           # [{action, result, is_error}] appended by execute_action
    iteration_count: int                 # incremented by plan_action
    llm_response: str                    # latest raw model reply (action or FINAL ANSWER)
    tokens_input: int                    # accumulated prompt tokens
    tokens_output: int                   # accumulated completion tokens
    charts: list[str]                    # Plotly figure JSON strings captured in execute_action

    # Output
    answer: str | None                   # final markdown answer (FINAL ANSWER stripped)
    selector_reasoning: str | None       # C19 selector rationale (persisted on the run)

    # Control
    error: str | None                    # set by any node on fatal failure → handle_error
    status: str                          # running | completed | failed
```

This replaces the skeleton's 4-field `AgentState`. `TypedDict, total=False` per skeleton convention (not dataclass/Pydantic).

---

## Nodes / Steps

### `setup`

**Reads:** `dataset_ids`, `session_id`, `run_id`. **Writes:** `dataset_context`, `error` (on fatal). **LLM:** no.

**Behaviour:** For each `dataset_id`, check the session DataFrame cache (C27) keyed by `session_id` — on hit reuse + LRU-touch; on miss load Parquet (preferred) or CSV (fallback) and cache. Single-turn (no `session_id`) uses a run-scoped `_dataframes[run_id]` dict instead. Build `dataset_context` from each dataset's notes/facts and column schema. A fatal load/lookup error sets `error` → routes to `handle_error`. (Cache logic lands in Phase 3; Phase 2's `setup` is the simple per-run load.)

| System | Operation | On Failure |
|--------|-----------|------------|
| Disk (`uploads/`) | read Parquet/CSV into DataFrame | fatal → set `error` |
| SQLite | load dataset metadata | fatal → set `error` |

### `plan_action`

**Reads:** `question`, `action_history`, `conversation_history`, `dataset_context`, `iteration_count`. **Writes:** `llm_response`, `iteration_count` (+1), `tokens_input`, `tokens_output`. **LLM:** yes — `plan_action.md` system prompt + assembled context + injected `<node:plan>` tag.

**Behaviour:** Assemble the prompt (question + Action/Result/Error transcript + conversation history + dataset context + persistent memory + column schema), call the LLM, store the reply, increment `iteration_count`, add token counts. When `iteration_count >= max_iterations - 2`, append a wrap-up instruction telling the model to produce `FINAL ANSWER:` now from its best findings (no extra LLM call). A fatal LLM error sets `error`.

### `execute_action`

**Reads:** `llm_response`, `action_history`, `iteration_count`, the loaded DataFrame(s). **Writes:** `action_history`, `charts`. **LLM:** no.

**Behaviour:** Eval/exec the pandas expression from `llm_response` in the sandbox namespace; capture any Plotly figures as JSON into `charts`; convert the result to a string; append `{action, result, is_error}` to `action_history`; write `iteration_count` to the DB each step for live progress polling (`GET /runs/current`). On exception, mark `is_error=true` and route back to `plan_action` to self-correct (recoverable). 3 consecutive errors OR max-iter → `force_finalize`. A non-recoverable fatal error → `handle_error`.

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | write `iteration_count` for live polling | log + continue |
| Disk | `save_dataset` writes CSV+Parquet | record error in step, route to plan_action |

### `finalize`

**Reads:** `llm_response`, `charts`, `action_history`, `run_id`. **Writes:** `answer`, `status=completed`. **LLM:** no.

**Behaviour:** Strip the leading `FINAL ANSWER:` prefix, append chart divs (from `charts`), set `status=completed`, persist `answer` + `action_history` + token counts to the `query_runs` row, release the run-scoped DataFrame.

### `force_finalize`

**Reads:** `action_history`, `question`, `run_id`. **Writes:** `answer`, `status=completed`. **LLM:** yes — ONE synthesis call with `finalize.md` + injected `<node:finalize>` tag.

**Behaviour:** Fires on max-iter OR 3 consecutive errors. One synthesis LLM call; `status` is ALWAYS `completed`; set `error_message = "max_iterations"` or `"consecutive_errors"` on the run (informational, not a failure). Falls back to a static best-effort message if the call fails.

### `handle_error`

**Reads:** `error`, `run_id`. **Writes:** `status=failed`. **LLM:** no.

**Behaviour:** Fatal errors → set `status=failed`, persist `error_message`, release the DataFrame, terminate.

---

## Graph / Flow Topology

```
START
  │
  ▼
setup ──(error)──► handle_error ──► END
  │ (ok)
  ▼
plan_action ──(fatal error)──────► handle_error ──► END
  │     │
  │     └──(FINAL ANSWER: in llm_response)──► finalize ──► END
  ▼ (action)
execute_action ──(fatal error)───► handle_error ──► END
  │     │
  │     └──(3 consec errors OR iteration_count ≥ max_iter)──► force_finalize ──► END
  ▼ (ok or recoverable error)
plan_action   (loop)
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `setup` | `state.get("error")` | `handle_error` |
| `setup` | else | `plan_action` |
| `plan_action` | `state.get("error")` | `handle_error` |
| `plan_action` | `"final answer:"` in `llm_response.lower()` | `finalize` |
| `plan_action` | else (an action to run) | `execute_action` |
| `execute_action` | `state.get("error")` (fatal) | `handle_error` |
| `execute_action` | 3 consecutive `is_error` OR `iteration_count >= max_iterations` | `force_finalize` |
| `execute_action` | else (ok / recoverable error) | `plan_action` |
| `finalize` / `force_finalize` / `handle_error` | always | `END` |

**Termination signal:** case-insensitive substring `FINAL ANSWER:` in `llm_response` (tolerate preamble before it). `MAX_ITERATIONS` = `settings.max_iterations` (env `AGENT_MAX_ITERATIONS`, default 6).

---

## Pre-flight (before the graph — two one-shot `LLMClient` calls)

Runs in the `/ask` handler / runner, BEFORE the graph, and is SKIPPED when explicit `dataset_ids` are supplied. Lives in `src/graph/preflight.py`.

1. **C26 clarification** — `check_clarification(question, schemas)` (tag `<node:clarify>` style): returns either a clarifying question (the run returns early `type:"clarification"`, status `clarification`, no graph run) or "proceed". Skipped when `skip_clarification=true`.
2. **C19 selector** — `select_datasets(question, all_schemas)` (tag `<node:select>`): returns the subset of dataset IDs to load; falls back to ALL datasets on failure. `selector_reasoning` persisted on the run.

---

## Graph-adjacent single LLM calls (not graph nodes)

- `generate_suggestions(question, answer)` (`src/graph/suggestions.py`) → up to 3 short follow-up questions (JSON array; `[]` on failure); tokens added to the run total.
- `generate_dataset_notes()` (`src/graph/describe.py`, C30) → sample 50 rows, ask for ≤300-word plain notes, write to `dataset.context`, track `auto_notes_status`, then trigger C31.
- `extract_facts()` (`src/graph/compress.py`, C31) → one LLM call → JSON array of ≤20 facts; fills `dataset.context_facts` and `settings.global_memory_facts`; async fire-and-forget self-heal variants with an in-flight lock; failures return `[]`.

---

## Stub provider node-tag branching

The stub provider (offline fallback) branches **only on the injected node tag**, never on prose keywords:

| Injected tag | Stub output |
|--------------|-------------|
| `<node:finalize>` | canned best-effort summary string |
| `<node:select>` | first dataset id from the schema block as a 1-element JSON array |
| `<node:plan>` (1st call) | `df.describe().to_string()` |
| `<node:plan>` (later call) | a `FINAL ANSWER:` markdown summary (iteration inferred from count of `Result:`/`Error:` markers so repeated calls differ) |
| `<node:plan>` missing | `FINAL ANSWER: [stub] Unable to process` |
| `<node:clarify>` | "proceed" (no clarification in stub mode) |
| `<node:suggest>` | `[]` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph `AgentState` | question, action_history, charts, tokens, iteration_count |
| **Across runs** | SQLite `settings` (`global_memory`, `global_memory_facts`) | user-authoritative global memory text + compressed facts, injected into every `plan_action` prompt |
| **Conversation** | `conversation_sessions` + `query_runs` (`session_id`) | prior turns; loaded into `conversation_history` for multi-turn |
| **Dataset notes** | `datasets.context` / `context_facts` | per-dataset notes injected into `dataset_context` |

**Context window management:** `dataset_context` uses notes/compressed facts rather than full data; `action_history` is the running transcript; the C29 `prompt_breakdown` measures each component (system_overhead, dataset_schemas, history, memory, dataset_notes, action_history, total_prompt). When approaching `max_iterations`, the wrap-up instruction forces a `FINAL ANSWER:` rather than growing the context further.

---

## Human-in-the-Loop Checkpoints

The pre-flight **clarification** (C26) is the only pause: an ambiguous question returns `type:"clarification"` with a `clarification_question`; the user re-submits with `skip_clarification:true`. No mid-run pauses.

---

## Error Handling & Recovery

**Node-level:** each node catches its own exceptions. Recoverable execution errors are recorded in `action_history` and looped back to `plan_action`. Fatal errors set `state["error"]` and route to `handle_error`.

**Graph-level (`handle_error`):** reads `state.error`, `state.run_id`; updates the `query_runs` row → `status=failed`, `error_message`; logs with `run_id` context; releases the DataFrame; terminates.

**Resume / retry:** no checkpointer — runs are short and single-shot; a failed run is re-issued as a new `/ask`. (No `SqliteSaver` needed; no long-running pause beyond the synchronous clarification short-circuit.)

**Partial failure:** a failed `save_dataset` or a failed chart capture is recorded as a step error and does not abort the run — the agent continues and finalizes with what it has. A failed `generate_suggestions` returns `[]`.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | one logical run per `run_id`, one log line per node | structlog (stdout, JSON) |
| **LLM calls** | accumulated `tokens_input`/`tokens_output`, model | `query_runs` row + structured log |
| **Tool calls** | each pandas action: expression, result/error | `query_runs.action_history` + log |
| **Run outcome** | status, iteration_count, error if any | `query_runs` row + log |

---

## Concurrency Model

- **Run isolation:** single-user, one run at a time per request; `GET /runs/current` returns the most recent run for ~1/s live polling. Runs are scoped by `run_id`; no global lock needed for the single-user model.
- **Parallel nodes within a run:** none — the ReAct loop is strictly sequential.
- **Checkpointing:** none (no `SqliteSaver`/`PostgresSaver`); runs are short-lived and not resumable. The C31 compression's async self-heal uses an in-flight lock (not a graph checkpoint).

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import setup, plan_action, execute_action, finalize, force_finalize, handle_error
from graph.edges import after_setup, after_plan, after_execute

def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("setup", setup)
    g.add_node("plan_action", plan_action)
    g.add_node("execute_action", execute_action)
    g.add_node("finalize", finalize)
    g.add_node("force_finalize", force_finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("setup")
    g.add_conditional_edges("setup", after_setup,
        {"plan_action": "plan_action", "handle_error": "handle_error"})
    g.add_conditional_edges("plan_action", after_plan,
        {"execute_action": "execute_action", "finalize": "finalize", "handle_error": "handle_error"})
    g.add_conditional_edges("execute_action", after_execute,
        {"plan_action": "plan_action", "force_finalize": "force_finalize", "handle_error": "handle_error"})
    g.add_edge("finalize", END)
    g.add_edge("force_finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```

`src/graph/runner.py` `run_agent(question, dataset_ids, session_id, ...)` creates the `query_runs` row (`status=running`), runs pre-flight (selector/clarification) unless explicit `dataset_ids`, invokes `agentic_ai`, persists the result, calls `generate_suggestions`, and returns the `/ask` payload.
