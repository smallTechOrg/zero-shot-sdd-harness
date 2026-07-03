# Agent

The LangGraph agent that answers one question about one dataset by writing pandas, running it locally, retrying on error, and composing the answer.

---

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Graph (LangGraph)** | Multi-step pipeline with a conditional retry loop. |

**Chosen:** **Graph (LangGraph)** composing three catalogue patterns from `harness/patterns/agentic-ai.md`: **LLM-Generated Code Execution (#22)** — the LLM writes executable pandas rather than mapping onto a rigid op-list; **Exception Handling & Recovery (#12)** — bounded retry when generated code errors; and **Prompt Chaining (#1)** — `generate_code → execute → write_answer` as an ordered two-LLM chain. Planning (#6) and Reflection (#4) are explicitly **deferred** (see below) — Phase 1 iterates only on hard execution errors, which is the smallest real "iterate-until-right".

**Phase 1 vs later:**
- **Phase 1:** the full skeleton below is wired — `load_context`, `generate_code`, `execute_code`, `write_answer`, `finalize`, `handle_error`, and the bounded retry edge.
- **Phase 2:** conversation history (`messages`) threaded into `generate_code`/`write_answer`; per-node progress events (SSE); token/cost capture. Same node set, richer state.
- **Deferred (beyond this build):** a `plan` node for big questions (Planning #6), a `reflect` node that re-runs when the result looks wrong (Reflection #4), a clarifying-question human-in-the-loop gate, and multi-dataset routing.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `generate_code` | Gemini | `gemini-3.1-pro` (repo default; `AGENT_LLM_MODEL` blank) | Code generation from schema needs the stronger model for correctness. |
| `write_answer` | Gemini | same (Phase 1); Phase 2 may downgrade via `AGENT_LLM_MODEL` | Turning an aggregated result into prose/chart selection is lighter — a cheaper model is a Phase-2 cost lever. |

**Fallback behaviour:** each LLM node wraps `LLMClient().call_model(...)` in try/except; on API error or rate-limit it sets `state["error"]` and routes to `handle_error`, which persists the run as `failed` with the message surfaced through the API. No offline/stub path — tests call the real Gemini API with keys from `.env`.

**Prompt strategy:** system prompt loaded from a `.md` file per node (matching the skeleton's `prompts/` convention). `generate_code` uses **structured output** — it must return only a fenced pandas code block that assigns a `result` dict; the node extracts the code. `write_answer` returns a single **JSON object** (answer, narrative, key_numbers, chart) parsed with a tolerant loader. Only schema + sample rows + question (+ prior error on retry) go to `generate_code`; only the question + aggregated result go to `write_answer`.

---

## Tools & Tool Calling

The LLM does not call tools via function-calling; it **emits code that the graph executes** (pattern #22). The executable surfaces are graph-owned functions, not LLM-invoked tools:

| Function | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `analysis.executor.run_pandas` | Runs generated pandas in a timed subprocess against the full dataset file | `code: str`, `data_path: str`, `timeout: int` | `(result: dict \| None, error: str \| None)` | Spawns a subprocess; reads the local data file; no writes |
| `analysis.charts.build_vega_spec` | Validates the LLM's chart selection and builds a Vega-Lite spec | `selection: dict`, `table: list[dict]` | Vega-Lite spec `dict` | None (pure) |
| `analysis.profiler.profile` | Profiles a DataFrame (used at upload, not in the graph) | `df: DataFrame` | profile `dict` | None (pure) |

**Tool selection strategy:** fixed order — the graph always generates code, always executes it, always writes the answer. No LLM routing in Phase 1.

**Tool failure handling:** `run_pandas` failures (non-zero exit, timeout, traceback) become an `exec_error` string that drives the bounded retry edge; after `AGENT_MAX_CODE_RETRIES` the run fails cleanly.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                     # set at initialisation by the runner
    dataset_id: str                 # set at initialisation

    # Input
    question: str                   # set at initialisation (the user's plain-language question)

    # Context (populated by load_context — NEVER the raw rows)
    schema: list[dict]              # [{name, dtype, null_count}, ...]
    sample_rows: list[dict]         # a few example rows for the prompt
    row_count: int                  # exact full-data row count
    data_path: str                  # local file path to the full dataset

    # Pipeline data (populated progressively)
    code: str                       # generated pandas (generate_code)
    exec_result: dict | None        # aggregated {value, table, columns} (execute_code)
    exec_error: str | None          # execution error, if any (execute_code) — drives retry
    attempts: int                   # generate→execute attempts so far

    # Output (populated by write_answer)
    answer_text: str                # plain-language answer with key numbers
    narrative: str                  # short interpretation
    key_numbers: list[dict]         # [{label, value}, ...]
    chart_spec: dict                # Vega-Lite spec
    table: list[dict]               # summary table rows (== exec_result.table)

    # Control
    error: str | None               # set by any node on fatal failure → handle_error
    status: str                     # "completed" | "failed"
    messages: list                  # chat-turn history (Phase 2; present but unused in Phase 1)
```

---

## Nodes / Steps

### `load_context`
**Reads from state:** `dataset_id`
**Writes to state:** `schema`, `sample_rows`, `row_count`, `data_path`, `attempts` (0)
**LLM call:** no.
**External calls:**
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Load the `datasets` row (profile JSON + file path) | fatal — set `error`, route to `handle_error` (dataset missing) |

**Behaviour:** hydrates the prompt context from the stored profile only. Never reads the full data file — that stays for the subprocess. Sets `attempts=0`.

### `generate_code`
**Reads from state:** `schema`, `sample_rows`, `row_count`, `question`, `exec_error` (on retry), `messages` (Phase 2)
**Writes to state:** `code`, `attempts` (+1)
**LLM call:** yes — Gemini, prompt `prompts/generate_code.md`. Output: a fenced pandas block assigning `result = {"value": ..., "table": [...], "columns": [...]}`. On retry the prior `code` + `exec_error` are appended so the model fixes its mistake.
**External calls:**
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | Generate pandas code | fatal — set `error`, route to `handle_error` |

**Behaviour:** produces code that computes a **compact aggregated** result (≤ ~200 rows) suitable for both the summary table and the chart. Only schema + sample rows leave the machine.

### `execute_code`
**Reads from state:** `code`, `data_path`
**Writes to state:** `exec_result` or `exec_error`
**LLM call:** no.
**External calls:**
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas subprocess | `run_pandas(code, data_path, timeout)` on the FULL dataset | non-fatal — capture as `exec_error` (drives retry), do not set `error` |

**Behaviour:** runs the generated code locally against all rows in a timed subprocess. Success → `exec_result`; any error/timeout → `exec_error` string. Raw data stays in the subprocess.

### `write_answer`
**Reads from state:** `question`, `exec_result`
**Writes to state:** `answer_text`, `narrative`, `key_numbers`, `chart_spec`, `table`
**LLM call:** yes — Gemini, prompt `prompts/write_answer.md`. Output: JSON `{answer, narrative, key_numbers, chart}`. `charts.build_vega_spec` turns the chart selection into a Vega-Lite spec using the aggregated table.
**External calls:**
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | Compose answer + choose chart | fatal — set `error`, route to `handle_error` |

**Behaviour:** only the aggregated result (never raw rows) is sent. If chart selection is invalid, `build_vega_spec` falls back to a sensible default (bar of the first categorical vs first numeric column) rather than failing the run.

### `finalize`
**Reads:** all output fields, `run_id`. **Writes:** `status="completed"`. Persists the run row with code, result, answer, narrative, key numbers, chart, table.

### `handle_error`
**Reads:** `error`, `run_id`. **Writes:** `status="failed"`. Persists `error_message`; logs with `run_id` context; terminates.

---

## Graph / Flow Topology

```
START
  │
  ▼
load_context ──(error)──► handle_error ──► END
  │
  ▼
generate_code ──(error)──► handle_error
  │
  ▼
execute_code
  │
  ├─(exec_error and attempts < MAX)──► generate_code   [retry loop]
  ├─(exec_error and attempts >= MAX)─► handle_error ──► END
  │
  └─(ok)──► write_answer ──(error)──► handle_error
                 │
                 ▼
              finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `load_context` | `state.get("error")` | `handle_error` |
| `load_context` | else | `generate_code` |
| `generate_code` | `state.get("error")` | `handle_error` |
| `generate_code` | else | `execute_code` |
| `execute_code` | `exec_error` and `attempts < AGENT_MAX_CODE_RETRIES` | `generate_code` |
| `execute_code` | `exec_error` and `attempts >= AGENT_MAX_CODE_RETRIES` | `handle_error` |
| `execute_code` | no `exec_error` | `write_answer` |
| `write_answer` | `state.get("error")` | `handle_error` |
| `write_answer` | else | `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state (`AgentState`) | schema, sample rows, generated code, result, answer |
| **Across runs** | SQLite (`runs`, `datasets`) | every question's code/result/answer/chart + the dataset profiles |
| **Conversation** | `messages` in state + `sessions` table (Phase 2) | prior question/answer turns for follow-ups; **unused in Phase 1** |

**Context window management:** only schema + a few sample rows + the question (+ prior error on retry) are ever in the `generate_code` prompt — never the full data — so the prompt stays small regardless of dataset size. Phase 2 caps threaded history to the last N turns.

---

## Human-in-the-Loop Checkpoints

None in Phase 1 or Phase 2 — the run is fully autonomous. (A clarifying-question gate before running is deferred beyond this build; see roadmap out-of-scope.)

---

## Error Handling & Recovery

**Node-level:** each LLM/DB node catches its own exceptions; fatal errors set `state["error"]` and route to `handle_error`. `execute_code` is deliberately non-fatal — a code error becomes `exec_error` and feeds the retry loop.

**Graph-level (`handle_error` node):**
- Reads: `state.error`, `state.run_id`
- Updates DB: run `status` → `failed`, `error_message`
- Logs error with `run_id` context
- Terminates the graph

**Resume / retry strategy:** the bounded generate→execute retry (`AGENT_MAX_CODE_RETRIES`, default 3) is the recovery mechanism — the model sees its prior code + error and fixes it. No cross-run checkpointing (runs are short).

**Partial failure:** if `write_answer`'s chart selection is invalid, the chart degrades to a default spec rather than failing the whole run — the answer, narrative, table, and code still return.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One structured log context per run keyed by `run_id`, one line per node entry/exit | structlog → stdout (JSON) |
| **LLM calls** | Node name, model, latency, prompt/response sizes (Phase 2 adds token counts + $ estimate) | structlog; Phase 2 also persists to the run row |
| **Code execution** | Generated code, subprocess exit status, retry count, error string | structlog + `runs` row |
| **Run outcome** | Status, total duration, error if any | `runs` row + structlog |

Structured logging is wired in Phase 1 (day one) via the existing `src/observability`. LangSmith is not used because the Gemini call goes directly through `google-genai` (not LangChain), so structured stdout logging is the Phase-1 observability surface; token/cost accounting is added in Phase 2.

---

## Concurrency Model

- **Run isolation:** one question at a time per user; the API handles a run synchronously and returns the full result. `run_id`-scoped state; no cross-run shared mutable state.
- **Parallel nodes within a run:** none — the pipeline is strictly sequential (each step depends on the prior).
- **Subprocess:** `execute_code` spawns one child process per execution with a timeout; it is joined/killed before the node returns.
- **Checkpointing:** none (runs are short-lived; no human-in-the-loop pause).

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    load_context, generate_code, execute_code, write_answer, finalize, handle_error,
)
from graph.edges import after_load, after_generate, after_execute, after_answer

def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_context", load_context)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("write_answer", write_answer)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("load_context")
    g.add_conditional_edges("load_context", after_load,
                            {"generate_code": "generate_code", "handle_error": "handle_error"})
    g.add_conditional_edges("generate_code", after_generate,
                            {"execute_code": "execute_code", "handle_error": "handle_error"})
    g.add_conditional_edges("execute_code", after_execute,
                            {"generate_code": "generate_code",   # bounded retry
                             "write_answer": "write_answer",
                             "handle_error": "handle_error"})
    g.add_conditional_edges("write_answer", after_answer,
                            {"finalize": "finalize", "handle_error": "handle_error"})
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```
