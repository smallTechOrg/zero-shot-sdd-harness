# Agent

LangGraph is in use, so this file is authoritative for the agent graph.

## Pattern Choice

A **ReAct-style plan→execute→verify→iterate loop** built on **LLM-Generated Code Execution**
(catalogue #22) — the LLM writes pandas code, the system runs it locally over the full data.
Composed with: **Planning** (#6, lightweight per-step), **Tool Use** (#5 — the executor is the
single tool), **Exception Handling and Recovery** (#12 — code errors feed regeneration),
**Guardrails** (#18 — restricted namespace + privacy prompt builder), and **Observability**
(#19 — structured step logging). We deliberately do NOT use multi-agent, reflection, or RAG in
Phase 1. See [agentic-ai.md](../harness/patterns/agentic-ai.md).

**Anti-pattern avoided:** no hardcoded op-list interpreter — the LLM always emits executable
code.

## State (`AgentState`, extends the skeleton TypedDict)

```python
class AgentState(TypedDict, total=False):
    run_id: str               # analyses row id
    dataset_id: str           # active dataset
    question: str             # user's plain-language question
    schema: dict              # column names + dtypes (data-derived, ALLOWED in prompt)
    sample: list[dict]        # bounded row sample (ALLOWED in prompt)
    aggregates: dict          # per-column aggregates (ALLOWED in prompt)
    plan: str                 # current step's intent
    code: str                 # latest LLM-generated pandas code
    exec_result: dict | None  # serialized result of local execution
    chart_spec: dict | None   # Vega-Lite spec
    answer: str               # final prose answer
    step: int                 # loop counter
    max_steps: int            # step cap (env-configurable, default 4)
    last_error: str | None    # execution/verify error fed back to codegen
    status: str               # running | completed | failed
    messages: list            # chat-turn history (Phase 2+)
```

> The prompt builder constructs LLM input from ONLY `schema`, `sample`, `aggregates`,
> `question`, `plan`, and `last_error` — never the full DataFrame. Raw rows live outside state,
> loaded by the executor from disk at execution time.

## Nodes

| Node | Does | LLM? | Sees raw data? |
|------|------|------|----------------|
| `plan` | Reads schema/sample/aggregates + question (+ last_error); produces a short intent for this step. | yes | no |
| `generate_code` | Emits pandas code that computes the answer over `df` and an optional chart spec. | yes | no |
| `execute` | Runs the code LOCALLY in the restricted namespace against the FULL DataFrame; captures result, chart_spec, or error. | no | yes (local only) |
| `verify` | Checks result is well-formed / non-empty / matches question shape; sets `last_error` to re-loop or routes to finalize. | no (rule-based; LLM optional later) | no |
| `finalize` | Assembles prose `answer` + chart_spec + code; sets status `completed`; persists. | yes (prose summary) | no |
| `handle_error` | On cap-hit or fatal error, sets status `failed` with a clear message and what was tried. | no | no |

`plan` and `generate_code` may be merged into one LLM call to save cost; kept separate in the
graph for traceability and split-by-config.

## Edges

- entry → `plan`
- `plan` → `generate_code`
- `generate_code` → `execute`
- `execute` → `verify`
- `verify` → conditional:
  - result valid → `finalize`
  - result invalid AND `step < max_steps` → increment `step`, set `last_error`, → `plan`
  - result invalid AND `step >= max_steps` → `handle_error`
  - executor raised a fatal (non-recoverable) error → `handle_error`
- `finalize` → END
- `handle_error` → END

## Error Handler

`handle_error` never crashes the agent: it records `last_error`, the final attempted `code`,
and a human-readable "here's what I tried" message, sets status `failed`, and the run row is
still persisted (audit holds even on failure). Recoverable execution errors (e.g. a bad column
name) loop back through `plan` with `last_error` set; only cap-hit or sandbox-fatal errors
terminate.

## Finalize

`finalize` produces the prose answer grounded in `exec_result` (numbers come from local
execution, NOT from the model inventing them), attaches the `chart_spec`, includes the exact
`code`, and updates the `analyses` row to `completed`.

## Concurrency

One agent invocation per analyze request; the loop is sequential (each step depends on the
prior result). Multiple requests are independent and isolated by `run_id`/`dataset_id`. The
executor loads the DataFrame per run (cached by dataset in later phases).

## Graph Assembly (pseudocode)

```python
def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("plan", plan)
    g.add_node("generate_code", generate_code)
    g.add_node("execute", execute)
    g.add_node("verify", verify)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("plan")
    g.add_edge("plan", "generate_code")
    g.add_edge("generate_code", "execute")
    g.add_edge("execute", "verify")
    g.add_conditional_edges(
        "verify",
        route_after_verify,   # -> "finalize" | "plan" | "handle_error"
        {"finalize": "finalize", "plan": "plan", "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```

`route_after_verify` enforces the step cap and the recoverable-vs-fatal distinction described
under Edges. The runner (`src/graph/runner.py`) creates the `analyses` row, invokes the graph,
and writes back the final state.
