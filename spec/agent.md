# Agent

The privacy-preserving analysis agent: a LangGraph pipeline that plans, generates pandas, executes it locally, and summarizes — with a hard privacy boundary between the LLM and raw data.

## Agent Architecture Pattern

**Chosen: Graph (LangGraph).** The flow is a multi-step pipeline with conditional edges (plan → generate code → execute locally → summarize), an error branch, and a privacy boundary that must be enforced node-by-node. A graph makes the boundary auditable and the steps streamable. Phase 3 adds a conditional `clarify` node and a `plan_confirm` human-in-the-loop interrupt.

## LLM Provider & Model

| Node | Provider | Model ID | Rationale |
|------|----------|----------|-----------|
| `plan` | Gemini | `gemini-2.0-flash` | fast structured plan from schema + history |
| `generate_code` | Gemini | `gemini-2.0-flash` | code from plan + schema |
| `summarize` | Gemini | `gemini-2.0-flash` | streamed plain-language answer from result summary |

**Fallback behaviour:** retry with exponential backoff (3 attempts) on transient Gemini errors; on persistent failure set `state.error` → `handle_error` → surfaced to the UI as a failed query. Tests call the real Gemini API via `.env`.

**Prompt strategy:** system + user split. `plan`/`generate_code` use JSON-structured output (plan steps; code in a single field). `generate_code` is instructed to assume a pre-loaded `df` and assign the result to a `result` variable. `summarize` streams natural-language tokens. Prompts in `src/prompts/{plan,codegen,answer}.md`.

## Tools & Tool Calling

This is a pipeline, not an LLM-driven tool loop; the "tool" is the local executor invoked deterministically by a node.

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `execute_pandas` | run generated code in sandbox subprocess against the local data file | code string, dataset file path | structured result (scalar / table / chart-spec) + stdout | reads local file; writes temp only |

**Tool selection strategy:** deterministic — `execute_locally` always runs after `generate_code`.
**Tool failure handling:** capture sandbox error; one repair attempt (feed error + code back to `generate_code`), then fail to `handle_error`.

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                      # query/run id, set at init
    session_id: str                  # conversation id
    dataset_id: str                  # active dataset

    # Input
    question: str                    # user's natural-language question
    messages: list                   # prior turns [{role, content}] — conversation memory

    # Privacy-safe context (LLM-visible)
    schema: dict                     # column names + dtypes
    profile: dict                    # column profiles/summaries (NO rows)

    # Pipeline data
    plan: str                        # analysis plan from `plan`
    code: str                        # pandas from `generate_code`
    exec_result: dict                # structured result from sandbox (local)
    result_summary: dict             # privacy-safe summary of exec_result for the LLM

    # Output
    answer: str                      # streamed plain-language answer
    repair_attempted: bool           # one-shot code repair guard

    # Control
    error: str | None
    status: str                      # "completed" | "failed"
```

## Nodes / Steps

### `plan`
- **Reads:** `question`, `schema`, `profile`, `messages`
- **Writes:** `plan`
- **LLM call:** yes — Gemini, JSON plan. **Receives schema + profile + history only.**
- **External calls:** Gemini (fatal on persistent failure → set error).
- **Behaviour:** decide the analysis approach from privacy-safe context.

### `generate_code`
- **Reads:** `plan`, `schema`, (`code` + `error` on repair)
- **Writes:** `code`, `repair_attempted`
- **LLM call:** yes — Gemini, returns pandas referencing `df`, assigning `result`. **No rows.**
- **Behaviour:** translate the plan into runnable pandas.

### `execute_locally`
- **Reads:** `code`, `dataset_id`
- **Writes:** `exec_result`, `result_summary`, possibly `error`
- **LLM call:** **no** — the only node touching raw rows; runs the sandbox subprocess.
- **External calls:** sandbox subprocess (error → repair path).
- **Behaviour:** load real file → `df`, run code, capture `result`, derive a privacy-safe `result_summary`.

### `summarize`
- **Reads:** `question`, `result_summary`
- **Writes:** `answer`
- **LLM call:** yes — Gemini, **streamed**. Receives `result_summary` only (aggregates, not rows).
- **Behaviour:** plain-language answer with key numbers.

### `handle_error`
- Sets `status="failed"`, persists `error`, logs with `run_id`, terminates.

### `finalize`
- Sets `status="completed"`, persists query + code + result + token usage, streams completion.

## Graph / Flow Topology

```
START
  │
  ▼
plan ──(error)──► handle_error ──► END
  │
  ▼
generate_code ──(error)──► handle_error
  │
  ▼
execute_locally ──(exec error & !repair_attempted)──► generate_code   (one repair loop)
  │              └─(exec error & repair_attempted)──► handle_error
  ▼
summarize ──(error)──► handle_error
  │
  ▼
finalize ──► END
```

**Conditional edges:**

| Source | Condition | Target |
|--------|-----------|--------|
| plan | `state["error"]` | handle_error |
| plan | else | generate_code |
| generate_code | `state["error"]` | handle_error |
| generate_code | else | execute_locally |
| execute_locally | exec error & not `repair_attempted` | generate_code |
| execute_locally | exec error & `repair_attempted` | handle_error |
| execute_locally | else | summarize |
| summarize | `state["error"]` | handle_error |
| summarize | else | finalize |

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | all in-progress data |
| Across runs | SQLite (`queries`, `datasets`) | past queries, code, results — audit trail + revisit |
| Conversation | `messages` in state, persisted per `session` (Phase 2) | prior turns so follow-ups work |

**Context window management:** Phase 2 truncates `messages` to the last N turns + a rolling summary; profiles are compact (no rows) so they fit easily.

## Human-in-the-Loop Checkpoints (Phase 3)

| Checkpoint | Shown | Action | Default |
|------------|-------|--------|---------|
| `clarify` | ambiguity question | user answers | only when genuinely ambiguous |
| `plan_confirm` | proposed plan | approve/edit | auto-proceed if no response in UI flow |

## Error Handling & Recovery

**Node-level:** each node try/excepts; fatal → `state.error` → `handle_error`.
**Graph-level (`handle_error`):** DB status `failed`, `error_message`, logs with `run_id`, terminates.
**Resume/retry:** sandbox exec errors get one repair loop; LLM errors get backoff retries.
**Partial failure:** chart-build failure (Phase 2) degrades to table-only, not a hard fail.

## Concurrency Model

- **Run isolation:** one query at a time per process (single user); SSE stream per query keyed by `run_id`.
- **Parallel nodes:** none in v1 (linear pipeline).
- **Checkpointing:** none in Phase 1; Phase 3 adds `SqliteSaver` for the `plan_confirm` interrupt.

## Graph Assembly (`src/graph/agent.py`)

```python
g = StateGraph(AgentState)
g.add_node("plan", plan)
g.add_node("generate_code", generate_code)
g.add_node("execute_locally", execute_locally)
g.add_node("summarize", summarize)
g.add_node("finalize", finalize)
g.add_node("handle_error", handle_error)

g.set_entry_point("plan")
g.add_conditional_edges("plan", route_after_plan,
    {"generate_code": "generate_code", "handle_error": "handle_error"})
g.add_conditional_edges("generate_code", route_after_codegen,
    {"execute_locally": "execute_locally", "handle_error": "handle_error"})
g.add_conditional_edges("execute_locally", route_after_exec,
    {"summarize": "summarize", "generate_code": "generate_code", "handle_error": "handle_error"})
g.add_conditional_edges("summarize", route_after_summarize,
    {"finalize": "finalize", "handle_error": "handle_error"})
g.add_edge("finalize", END)
g.add_edge("handle_error", END)

agentic_ai = g.compile()
```
