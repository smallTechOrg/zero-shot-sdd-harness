# Agent

> The plan → write-code → execute-locally → observe → retry loop for the Local CSV Analyst, wired in the boilerplate's LangGraph `StateGraph(AgentState)` (compiled as `agentic_ai` in `src/graph/agent.py`, entry `src/graph/runner.py::run_agent`).

---

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Graph (LangGraph)** | Multi-step pipeline with conditional edges, checkpointing, or parallel nodes. |

**Chosen:** **Graph (LangGraph)** composing **Planning** (`agentic-ai.md#6`) + **LLM-Generated Code Execution** (`#22`) + **Reflection/retry** (`#4` + `#12` exception-handling) + observability (`#19`). The agent plans, generates pandas, runs it locally, observes the result, and reflects-and-retries on failure with the error fed back — up to a cap. This is the right level: there are real tools (local code execution) and a real branch (success vs retry-with-error), so it is above a single call but below multi-agent. We deliberately do **not** use multi-agent — one graph with a code-execution tool suffices.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `plan` | Gemini | `gemini-3.1-pro` | One short plan from schema+sample+question. Cheap: tiny prompt, ~3–5 line plan output. |
| `generate_code` | Gemini | `gemini-3.1-pro` | Writes pandas from schema+sample+question (+prior error on retry). The accuracy-critical call; same model, small prompt. |

No other node calls the LLM. `LLMClient().call_model(prompt, system=...)` auto-selects Gemini from `AGENT_GEMINI_API_KEY`; model overridable via `AGENT_LLM_MODEL`.

**Fallback behaviour:** if the Gemini API errors or rate-limits, the node sets `state["error"]` and the graph routes to `handle_error` (run `failed`, error surfaced to the UI). No offline/stub path — tests call the real Gemini API with keys from `.env`. Single-user: the user simply re-asks.

**Prompt strategy:** system/user split. System prompt (in `src/prompts/plan.md` and `src/prompts/code.md`) instructs: "You are given ONLY the schema and a few sample rows — never the full data. Write pandas over a DataFrame named `df` that assigns `result`, and optionally `chart` and `table`." `generate_code` requests **code only** (fenced block), parsed out before execution. Keep prompts terse to minimize tokens.

---

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `sandbox.run_code` | Run generated pandas in a local subprocess over the FULL file | `csv_paths`, `code`, `timeout` | `SandboxResult{ ok, result, chart, table, stdout, error }` | Spawns a child Python process; reads local CSV; no network. |

**Tool selection strategy:** not LLM-chosen — the graph deterministically calls `sandbox.run_code` in the `execute_code` node with the latest generated code. The LLM's only "action" is producing code.

**Tool failure handling:** a sandbox failure (exception / non-zero exit / timeout) is captured as `SandboxResult.error` and fed back into `generate_code` for a corrected attempt, up to `max_retries`. After the cap, route to `handle_error`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                          # set at init by run_agent
    dataset_id: str                      # which dataset this run targets
    csv_paths: dict[str, str]            # {name: local_path} — full file(s); name "df" in Phase 1

    # Input  (the ONLY things derived for the LLM — see Privacy Boundary)
    question: str                        # the user's plain-English question
    schema: list[dict]                   # [{name, dtype}] — column names + dtypes
    sample_rows: list[dict]              # ≤ 20 sample rows (for the prompt only)

    # Pipeline data (populated progressively by nodes)
    plan: str | None                     # short plan from `plan` node
    code: str | None                     # latest generated pandas (from generate_code)
    attempts: list[dict]                 # audit trail: [{code, error|null, ok}] per try
    retries: int                         # how many regen attempts so far
    max_retries: int                     # cap (default 3)
    last_error: str | None               # last sandbox/LLM error fed back to generate_code

    # Output
    answer: str | None                   # plain-English answer (finalize)
    chart_spec: dict | None              # Plotly JSON (built by execute_code/finalize)
    table: list[dict] | None             # summary table as JSON records

    # Telemetry (cheap, Phase 1 captures tokens; cost surfaced Phase 5)
    tokens: int                          # accumulated LLM tokens this run

    # Control
    error: str | None                    # set on fatal failure → handle_error
    status: str | None                   # "completed" | "failed" (set by finalize/handle_error)
    messages: list                       # chat-turn history (skeleton field; used from Phase 3)
```

---

## Nodes / Steps

### `plan`

**Reads from state:** `question`, `schema`, `sample_rows`
**Writes to state:** `plan`, `tokens`, (`error` on LLM failure)
**LLM call:** yes — `src/prompts/plan.md` system + (schema + sample + question) user → a 3–5 line plain-English plan. Model `gemini-3.1-pro`.
**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | one cheap completion | fatal → set `error` |

**Behaviour:** produces a short plan ("filter X, group by Y, count, bar chart") streamed to the UI so the user sees intent before code runs. Privacy: only schema+sample+question in the prompt.

### `generate_code`

**Reads from state:** `question`, `schema`, `sample_rows`, `last_error` (on retry), `plan`
**Writes to state:** `code`, `tokens`, (`error` on LLM failure)
**LLM call:** yes — `src/prompts/code.md` system + (plan + schema + sample + question + prior error if any) → a fenced pandas block assigning `result`/`chart`/`table`. Model `gemini-3.1-pro`. Code is parsed out of the fenced block.
**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | one cheap completion | fatal → set `error` |

**Behaviour:** writes pandas from schema+sample (NOT data). On a retry, the previous `last_error` is included so the model corrects its approach (reflection). Streams a "writing code" / "rewriting code (retry N)" step.

### `execute_code`

**Reads from state:** `code`, `csv_paths`
**Writes to state:** appends to `attempts`; on success sets `result`-derived `answer` seed, `chart_spec`, `table`; on failure sets `last_error`, increments `retries`
**LLM call:** **no** — local only.
**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| `sandbox.run_code` (local subprocess) | load FULL csv, run code, capture result/chart/table | non-fatal → record `last_error`, route to retry/observe |

**Behaviour:** the **only** node that touches the full data, and it never calls the LLM. Streams "running code". Builds the Plotly `chart_spec` from the child's `chart` descriptor + data, and the JSON `table`.

### `observe` (routing logic, implemented in `edges.py`)

Decides, after `execute_code`, whether the attempt succeeded → `finalize`; failed and `retries < max_retries` → `generate_code` (with `last_error`); failed and cap reached → `handle_error`.

### `finalize`

**Reads from state:** `result`/answer-seed, `chart_spec`, `table`, `plan`, `attempts`
**Writes to state:** `answer`, `status="completed"`
**LLM call:** **no** — Phase 1 composes the plain-English answer deterministically from the result + a templated sentence (the result is already the aggregate the user asked for). *(A later phase may add one cheap LLM call to phrase the answer; not needed for Phase 1.)*
**Behaviour:** marks the run completed; the runner persists answer + chart_spec + table + full `attempts` audit trail.

### `handle_error`

**Reads from state:** `error` or `last_error`, `run_id`, `attempts`
**Writes to state:** `status="failed"`
**Behaviour:** terminal failure node — persists status `failed` + the last error + the full `attempts` trail (so even a failed run is auditable). Streams a final "gave up after N attempts" step with the error.

---

## Graph / Flow Topology

```
START
  │
  ▼
plan ──(error)──────────────────────────► handle_error ──► END
  │
  ▼
generate_code ──(error)─────────────────► handle_error
  │
  ▼
execute_code
  │
  ├──(ok)──────────────────────────────► finalize ──► END
  │
  ├──(failed & retries < max_retries)──► generate_code   (last_error fed back)
  │
  └──(failed & retries >= max_retries)─► handle_error ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `plan` | `state["error"]` set | `handle_error` |
| `plan` | otherwise | `generate_code` |
| `generate_code` | `state["error"]` set | `handle_error` |
| `generate_code` | otherwise | `execute_code` |
| `execute_code` | last attempt `ok` | `finalize` |
| `execute_code` | failed & `retries < max_retries` | `generate_code` |
| `execute_code` | failed & `retries >= max_retries` | `handle_error` |

---

## Privacy Boundary

**HARD CONSTRAINT.** The LLM is called in exactly two nodes — `plan` and `generate_code` — and both receive ONLY: `schema` (column names + dtypes), `sample_rows` (≤ 20 rows derived once at upload/profile time), the `question`, and on retry the prior `last_error`. The full DataFrame exists ONLY inside `execute_code`'s local subprocess and is never serialized into any prompt. This is enforced by construction (the prompt builders take only those fields) and **asserted in tests**: a test inspects the prompt string passed to `LLMClient` and asserts it contains the schema/sample but none of the full-file rows beyond the sample. See [`spec/architecture.md`](architecture.md#local-code-execution-sandbox-detail).

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph `AgentState` | plan, code, attempts, result, chart, table |
| **Across runs** | SQLite (`runs`, `datasets`) | full audit trail per run (Phase 1) |
| **Conversation** | `AgentState.messages` + persisted session | chat-turn history — wired from **Phase 3** (resumable sessions); Phase 1 is single-shot per run |

**Context window management:** prompts are intentionally tiny (schema + ≤ 20 sample rows + question). No RAG, no full-data context. Keeps tokens — and cost — low.

---

## Human-in-the-Loop Checkpoints

None. Read-only analysis on local data; no irreversible actions. (Not applicable.)

---

## Error Handling & Recovery

**Node-level:** each node wraps its work in try/except; an LLM failure sets `state["error"]`. A sandbox failure is non-fatal — it's captured as `last_error` and drives the retry loop, not an immediate abort.

**Graph-level (`handle_error` node):**
- Reads: `state["error"]` / `state["last_error"]`, `state["run_id"]`, `state["attempts"]`
- Persists: run status → `failed`, `error_message`, the full `attempts` trail
- Logs the error with `run_id` context (structured stdout log)
- Terminates the graph

**Resume / retry strategy:** the retry loop (generate_code ↔ execute_code) is the recovery mechanism within a run, capped at `max_retries` (default 3). A fully failed run is not auto-resumed — the user re-asks. No LangGraph checkpointer in Phase 1 (runs are short).

**Partial failure:** if code runs but produces no chartable result, `finalize` still returns the text answer + table and omits the chart (the UI shows "no chart for this result") — degrade, not abort.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | one structured log line per node transition (run_id, node, latency) | stdout structured log |
| **LLM calls** | prompt+response summary, token count, latency, model | stdout structured log (per `plan` / `generate_code`) |
| **Tool calls** | `sandbox.run_code` code-hash, ok/error, duration | stdout structured log + persisted in `attempts` |
| **Run outcome** | status, total duration, error | SQLite `runs` + structured log |

Observability is wired in **Phase 1** (structured request/response + per-node logging to stdout) — never deferred. (Gemini, not LangChain/LangSmith, so no LangSmith tracing; structured logging is the observability surface.)

---

## Concurrency Model

- **Run isolation:** runs are scoped by `run_id`; each run is an independent `agentic_ai.invoke`. Single-user, so contention is minimal; the sandbox subprocess isolates execution per run.
- **Parallel nodes within a run:** none — the pipeline is strictly sequential (plan → code → execute → …).
- **Checkpointing:** none in Phase 1 (short runs). The audit trail in `runs.steps_json` is the durable record.

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import plan, generate_code, execute_code, finalize, handle_error
from graph.edges import after_plan, after_generate_code, after_execute

def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("plan")
    g.add_conditional_edges("plan", after_plan,
        {"generate_code": "generate_code", "handle_error": "handle_error"})
    g.add_conditional_edges("generate_code", after_generate_code,
        {"execute_code": "execute_code", "handle_error": "handle_error"})
    g.add_conditional_edges("execute_code", after_execute,
        {"finalize": "finalize", "generate_code": "generate_code", "handle_error": "handle_error"})
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```

`after_execute` returns `"finalize"` on success, `"generate_code"` if failed and `retries < max_retries`, else `"handle_error"`.
