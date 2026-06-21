# Plan-and-Execute

**Category:** Loop & Reasoning  
**Status:** Extended

## Intent

Separate planning from execution: one LLM call produces a complete multi-step plan upfront, then a separate executor works through each step sequentially, optionally replanning when unexpected results occur.

## When to use

- When the full scope of a task is knowable before any execution starts
- When steps are mostly independent (each doesn't require the previous step's result to be planned)
- When you need deterministic, auditable execution — the plan is visible and reviewable before any action
- When task complexity exceeds what a single-prompt ReAct loop handles reliably

**Do not use** when steps are highly interdependent — if step 3 depends on what step 2 actually returned (not just what you expected it to return), use a ReAct loop instead.

## How it works

```
Planner (LLM call 1)
  Input:  user goal + available tools
  Output: ordered list of steps
         │
         ▼
[Step 1] Executor (LLM call or direct tool call)
         │
         ▼
[Step 2] Executor
         │
         ├──(unexpected result) ─► Replanner (LLM call N)
         │                         Output: revised remaining steps
         │                         ──► continue executing revised steps
         ▼
[Step N] Executor
         │
         ▼
       Synthesizer (LLM call)
         Input:  original goal + all step results
         Output: final answer
```

### Planner output format (example)

```yaml
plan:
  goal: "Find the top-grossing film of 2024 and check if it's on Netflix."
  steps:
    - id: 1
      description: "Search for top-grossing film of 2024"
      tool_name: web_search
      capability_name: search
      arguments: { query: "top grossing film 2024" }
    - id: 2
      description: "Check Netflix availability"
      tool_name: netflix_api
      capability_name: check_availability
      arguments: { title: "<result from step 1>" }
    - id: 3
      description: "Synthesize final answer"
      type: synthesis
```

## Key components

1. **Planner node** — receives goal + tool list; produces the step list in a structured format
2. **Executor node** — iterates through steps; calls tools; collects results
3. **Replanner node** (optional) — receives completed steps + unexpected result; revises remaining steps
4. **Synthesizer node** — receives all step results; produces the final answer

## Variants

| Variant | Description |
|---|---|
| **No replanning** | Fixed plan, executed to completion even if intermediate results are unexpected |
| **Reactive replanning** | After each step, check if the result warrants revising remaining steps |
| **Validate-then-execute** | Show the plan to the user or a guardrail check before executing any step |
| **Parallel plan** | Planner identifies which steps can run in parallel; executor launches them concurrently (converges with [03-execution-plan.md](03-execution-plan.md)) |

## Comparison with ReAct

| Dimension | ReAct | Plan-and-Execute |
|---|---|---|
| LLM calls per step | 1 (plan_action + invoke_tool) | Planner is called once; executor may call LLM per step |
| Visibility | Implicit — plan emerges from tool_call_history | Explicit — plan exists as a document |
| Adaptability | Highly reactive — re-evaluates after every tool call | Lower — replanning is triggered, not automatic |
| Cost | More LLM calls for the same task | Fewer, but each call may be longer |
| Best for | Tasks where intermediate results redirect the plan | Tasks where the full plan is predictable |

## Related patterns

- [01-react-loop.md](01-react-loop.md) — the reactive alternative; most production agents prefer ReAct for its adaptability
- [03-execution-plan.md](03-execution-plan.md) — the execution plan format is a structured form of this pattern
- [07-chain-of-thought.md](07-chain-of-thought.md) — CoT is often used in the planner step to produce a higher-quality plan
- [15-human-in-the-loop.md](15-human-in-the-loop.md) — plan-and-execute is a natural fit for HITL review: pause after planning, resume after human approves

## Implementation notes

- The Planner should be prompted to produce a plan that assumes tool outputs will match expectations, then note any steps that depend on previous results with a placeholder like `<result from step N>`.
- Do not pass the entire plan to the executor in one context block — pass only the current step plus a summary of completed steps. Context grows quickly.
- Validate the plan structure immediately after the Planner call; if it is malformed, retry the Planner with a correction request before executing anything.
