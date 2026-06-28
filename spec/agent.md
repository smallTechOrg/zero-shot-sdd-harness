# Agent — Pandora Analysis Graph (LangGraph)

The agent turns a question + a dataset profile into a locally-executed answer. It is built on **LangGraph** (`src/graph/`), extending the skeleton's compiled `StateGraph` in place.

## Chosen Patterns (from `harness/patterns/agentic-ai.md`)

- **#22 LLM-Generated Code Execution** — the core. The LLM writes pandas; the system runs it on the full dataset. Never a hardcoded op-list (the anti-pattern the catalogue warns against).
- **#5 Tool Use** — the sandbox executor is the agent's one tool: code in → result out.
- **#12 Exception Handling & Recovery** — a single bounded **retry-on-error**: on a static-reject / runtime error / timeout, feed the error back to code-gen once, regenerate, re-run.
- **#18 Guardrails** — static validation of generated code before execution (reject `import`/`open`/`os`/`eval`/dunder) + the privacy boundary (schema-only to the LLM).
- **#16 Resource-Aware Optimization** — cheap default model, exactly two LLM calls per question (generate + summarise), cost accounting.
- **#19 Evaluation & Monitoring** — structured per-question logging; full-data correctness gate.
- **#8 Memory Management** — *Phase 2:* short-term conversation turns in state (prior Q/A summaries, never raw rows).
- **#6 Planning + #4 Reflection + #11 Goal Monitoring** — *Phase 4 only (deferred):* the bounded plan-then-execute / iterate-until-right depth. Labelled below; NOT in Phase 1.

**Why this set:** the task is "answer arbitrary questions over structured data" — pattern #22 is mandated. A single ReAct-style pass with one tool (the executor) and one retry is the smallest *real* agent that meets the Phase-1 bar; planning/reflection add latency+cost and are reached for only when a single pass demonstrably cannot answer (Phase 4), per the catalogue's "reach up only on a concrete need."

## State

```python
# src/graph/state.py
class AgentState(TypedDict, total=False):
    run_id: str                 # question id (persisted row)
    dataset_id: str
    dataset_path: str           # Parquet path passed to the sandbox
    profile: dict               # DatasetProfile — the ONLY dataset info given to the LLM
    question: str
    messages: list              # Phase 2: prior-turn summaries (role/content); never raw rows

    code: str | None            # latest generated pandas snippet
    exec_result: dict | None    # sandbox result: {result, chart_spec, ...}
    attempts: int               # retry counter (0 → 1 max in Phase 1)
    last_error: str | None      # fed back to code-gen on retry

    answer_text: str | None     # plain-language summary (markdown)
    chart_spec: dict | None     # {type, x, y, series} for recharts
    summary_table: dict | None  # {columns, rows} capped at MAX_RESULT_ROWS

    usage: dict                 # accumulated {prompt_tokens, completion_tokens, cost_usd}
    status: str                 # "completed" | "failed" | "stuck"
    error: str | None           # terminal user-facing error

    # Phase 4 (deferred — present but unused until then):
    plan: list | None           # ordered steps
    step_index: int             # current plan step
    max_steps: int              # bounded loop cap
```

## Nodes

| Node | Phase | Does | LLM call? |
|------|-------|------|-----------|
| `generate_code` | 1 | Builds the code-gen prompt from `profile` + `question` (+ `last_error` on retry); Gemini returns a pandas snippet assigning `result` (and optional `chart_spec`). Accumulates `usage`. | yes (gemini-2.5-flash) |
| `validate_code` | 1 | Static guard: reject `import`/`open`/`os`/`subprocess`/`eval`/`exec`/dunder/file access. On reject → set `last_error`. | no |
| `execute_code` | 1 | Calls `sandbox.executor.run_code(code, dataset_path)`. Stores `exec_result` or `last_error` + `kind`. | no |
| `summarise` | 1 | Gemini turns the (small) `exec_result` + question into plain-language `answer_text` (markdown), finalises `chart_spec` + `summary_table`. Accumulates `usage`. | yes (gemini-2.5-flash) |
| `handle_error` | 1 | Terminal: sets `status="stuck"`, `error` = a human "here's what I tried" message including the last code + error. | no |
| `finalize` | 1 | Sets `status="completed"`. | no |
| `plan` / `reflect` | 4 (deferred) | Bounded plan-then-execute + reflect-on-result loop. Stubbed/absent until Phase 4. | yes |

## Edges (Phase 1)

```
START → generate_code → validate_code
validate_code ─ valid ──▶ execute_code
              └ invalid ─▶ (retry?) generate_code | handle_error

execute_code ─ ok ───────▶ summarise
             └ error ─────▶ (retry?) generate_code | handle_error

summarise ─ ok ──────────▶ finalize
          └ error ────────▶ handle_error

finalize → END
handle_error → END
```

**Retry policy (the only loop in Phase 1):** `after_validate` / `after_execute` route to `generate_code` when `attempts < MAX_ATTEMPTS (=1)` — i.e. one regeneration with the error fed back — otherwise to `handle_error`. `attempts` increments on each regeneration. This is bounded and cannot loop forever.

```python
# src/graph/edges.py (Phase 1)
MAX_ATTEMPTS = 1

def after_validate(s):
    if s.get("last_error"):
        return "generate_code" if s["attempts"] < MAX_ATTEMPTS else "handle_error"
    return "execute_code"

def after_execute(s):
    if s.get("last_error"):
        return "generate_code" if s["attempts"] < MAX_ATTEMPTS else "handle_error"
    return "summarise"

def after_summarise(s):
    return "handle_error" if s.get("error") else "finalize"
```

## Graph Assembly (Phase 1)

```python
# src/graph/agent.py
def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("generate_code", generate_code)
    g.add_node("validate_code", validate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("summarise", summarise)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)
    g.set_entry_point("generate_code")
    g.add_edge("generate_code", "validate_code")
    g.add_conditional_edges("validate_code", after_validate,
        {"execute_code": "execute_code", "generate_code": "generate_code", "handle_error": "handle_error"})
    g.add_conditional_edges("execute_code", after_execute,
        {"summarise": "summarise", "generate_code": "generate_code", "handle_error": "handle_error"})
    g.add_conditional_edges("summarise", after_summarise,
        {"finalize": "finalize", "handle_error": "handle_error"})
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```

## Runner & Streaming

`src/graph/runner.py` — `run_agent_stream(dataset_id, question, conversation=None)` is a generator: it creates the `questions` row, builds the initial state (loading `profile` + `dataset_path` from the `datasets` row), then iterates `agentic_ai.stream(...)` yielding a step event per node boundary (mapped to the SSE step names in [architecture.md](architecture.md#streaming-step-updates)). On completion it persists `code`, `result`, `usage`, `status` and yields the final answer (or error) event. The API route (`src/api/questions.py`) wraps this generator in an `sse-starlette` `EventSourceResponse`.

## Concurrency

Single-user, low concurrency. The graph is compiled once at import. Each question runs the graph synchronously inside one SSE request; the sandbox subprocess is the only child process and is per-question (no shared sandbox state). Multiple concurrent questions are not expected but are safe — each has its own state, its own subprocess, and its own `questions` row; SQLite writes are short and serialised by the session.

## Error Handler & Finalize

- `handle_error` never raises — it produces a user-facing `error` string that includes the last attempted code and the underlying error (`static_reject` / `runtime_error` / `timeout` / `memory`), so the UI's "show what it tried" is satisfied even on failure. `status="stuck"`.
- `finalize` sets `status="completed"`; the runner persists the final state regardless of path so every question has a durable record (success or stuck) with its cost.

## Deferred Depth (Phase 4 — explicitly NOT Phase 1)

The plan-then-execute / iterate-until-right architecture adds `plan` and `reflect` nodes wrapping the existing execute loop: `plan` decomposes the question into ordered steps; each step runs generate→execute; `reflect` checks the intermediate result against the step goal and either advances `step_index` or revises; a bounded `max_steps` counter + goal-monitoring (#11) stops the loop. Model escalation (#16) bumps `gemini-2.5-flash`→`gemini-2.5-pro` when stuck. A SQL executor (DuckDB) becomes a second tool selected by a router (#2). None of this ships in Phase 1 — the Phase-1 graph above is complete and self-contained.
