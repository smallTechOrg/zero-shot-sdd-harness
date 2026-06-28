# Agent

---

## Agent Architecture Pattern

**Chosen:** Graph (LangGraph) — a plan-and-execute pipeline. The request is multi-step with a conditional self-correction loop and an error path, so a deterministic graph beats a free ReAct loop: profile context → plan → generate code → execute locally → (retry on failure) → visualize → finalize. This extends the skeleton's compiled `agentic_ai` graph in place.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| plan | Gemini | gemini-2.5-flash | fast strategy step, many/day |
| generate_code | Gemini | gemini-2.5-flash | code from profile+sample; fast |
| visualize | Gemini | gemini-2.5-flash | chart-type + follow-up choice |
| execute_local | — | — | no LLM; runs locally |

**Fallback behaviour:** Gemini calls retry once with backoff. On persistent failure, the node sets `state["error"]` and routes to `handle_error`; the executor's self-correction returns a best-guess flagged with assumptions rather than crashing. No offline/stub path — tests use the real key from `.env`.

**Prompt strategy:** system/user split. System prompt (`src/prompts/`) states the privacy contract, the available dataframe variable, and required structured output. Code generation requests JSON-or-fenced-code output parsed to plain code text. The context builder is the single chokepoint that injects ONLY profile + N-row sample + question + prior turns (see [privacy boundary](./architecture.md#privacy-boundary)).

---

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| execute_code_local | runs generated pandas/DuckDB code against the dataset file, dataframe pre-loaded as `df` | code: str, dataset file path | result frame (JSON), stdout, traceback | reads file; no network/FS-write by generated code |

**Tool selection strategy:** rule-based — the graph always calls the local executor after `generate_code`; the LLM does not choose tools.

**Tool failure handling:** on traceback, capture it, feed it back into one self-correction generate→execute pass; if still failing, return best-guess + "what I tried".

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                      # turn id; set at initialisation
    dataset_id: str                  # input
    conversation_id: str             # input

    # Input
    question: str                    # input (user)
    profile: dict                    # loaded from Dataset
    sample_rows: list                # loaded from Dataset (capped N)
    file_path: str                   # loaded from Dataset
    history: list                    # prior turns [{question, answer}, ...]

    # Pipeline data (populated progressively)
    plan: list                       # generate by plan node
    code: str                        # by generate_code
    result_table: dict               # by execute_local
    traceback: str | None            # by execute_local on failure
    retry_count: int                 # self-correction guard (max 1)
    answer: str                      # by visualize/summarize
    chart_spec: dict                 # by visualize
    follow_ups: list                 # by visualize
    assumptions: list                # set when best-guessing

    # Output / accounting
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    status: str                      # "completed" | "failed"

    # Control
    error: str | None
    checkpoint: str | None
```

The skeleton's `messages`/`input_text`/`output_text` fields are superseded by the above (kept for back-compat but unused on the analysis path).

---

## Nodes / Steps

### `load_context`
**Reads:** dataset_id, conversation_id, question. **Writes:** profile, sample_rows, file_path, history.
**LLM call:** no. **External:** SQLite read (fatal on missing dataset). Loads the privacy-safe context.

### `plan`
**Reads:** profile, sample_rows, question, history. **Writes:** plan, token usage.
**LLM call:** yes — Gemini, profile+sample only, returns step list.

### `generate_code`
**Reads:** plan, profile, sample_rows, question, traceback (if retrying). **Writes:** code, token usage.
**LLM call:** yes — Gemini, returns pandas/DuckDB code text.

### `execute_local`
**Reads:** code, file_path. **Writes:** result_table, traceback.
**LLM call:** no. **External:** local executor. On traceback with retry_count<1 → route back to generate_code; else continue with best-guess + assumptions.

### `visualize`
**Reads:** result_table, profile, question. **Writes:** answer, chart_spec, follow_ups, token usage.
**LLM call:** yes — Gemini, picks chart type + drafts answer + 2-3 follow-ups.

### `finalize`
**Reads:** all output fields. **Writes:** status="completed". Persists the [Turn](./data.md#entity-turn) audit record incl. cost.

### `handle_error`
**Reads:** error, run_id. **Writes:** status="failed". Persists failed Turn with error_message.

---

## Graph / Flow Topology

```
START
  │
  ▼
load_context ──(error)──► handle_error ──► END
  │
  ▼
plan ──(error)──► handle_error
  │
  ▼
generate_code ──(error)──► handle_error
  │
  ▼
execute_local ──(traceback & retry<1)──► generate_code
  │   │
  │   └──(error, no retry left)──► handle_error
  ▼
visualize ──(error)──► handle_error
  │
  ▼
finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| load_context / plan / generate_code / visualize | `state["error"]` is not None | handle_error |
| execute_local | `traceback` and `retry_count < 1` | generate_code |
| execute_local | `traceback` and retry exhausted | visualize (best-guess) |
| execute_local | success | visualize |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | in-progress plan/code/result |
| Across runs | SQLite | datasets, full audit trail of turns |
| Conversation | Turn rows ordered by created_at, injected as `history` | prior question/answer pairs for follow-ups |

**Context window management:** profile is compact; sample capped at N rows; history truncated to the last K turns (default 6) to stay within limits.

---

## Human-in-the-Loop Checkpoints

None. The agent answers autonomously; ambiguity is handled by a flagged best-guess, not a pause.

---

## Error Handling & Recovery

**Node-level:** each node try/excepts; fatal → `state["error"]` → `handle_error`.
**Graph-level (handle_error):** persists Turn with status="failed", error_message, timestamps; logs with run_id; terminates.
**Resume/retry:** code-execution failures self-correct once (generate_code re-entry). LLM calls retry once. No cross-run resume.
**Partial failure:** if visualize's chart choice fails, degrade to table-only (no crash). If execution can't be fixed, return best-guess + assumptions.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Trace | one trace per turn, span per node | stdout structured log (skeleton `observability/events`) |
| LLM calls | prompt/completion tokens, latency, model, estimated cost | structured log + Turn row |
| Tool calls | executor success/error, latency, traceback | structured log |
| Run outcome | status, duration, error | DB Turn + log |

---

## Concurrency Model

- **Run isolation:** single-user; turns processed one at a time per conversation. No 409 needed at MVP.
- **Parallel nodes within a run:** none — strictly sequential pipeline.
- **Checkpointing:** none required (no human-in-the-loop; turns are short).

---

## Graph Assembly (`graph/agent.py`)

```python
graph = StateGraph(AgentState)
graph.add_node("load_context", load_context)
graph.add_node("plan", plan)
graph.add_node("generate_code", generate_code)
graph.add_node("execute_local", execute_local)
graph.add_node("visualize", visualize)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("load_context")

for n in ("load_context", "plan", "generate_code", "visualize"):
    graph.add_conditional_edges(n, lambda s: "handle_error" if s.get("error") else _NEXT[n],
                                {"handle_error": "handle_error", _NEXT[n]: _NEXT[n]})

graph.add_conditional_edges("execute_local", route_after_execute,
    {"generate_code": "generate_code", "visualize": "visualize", "handle_error": "handle_error"})

graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)
compiled_graph = graph.compile()  # exported as agentic_ai
```
