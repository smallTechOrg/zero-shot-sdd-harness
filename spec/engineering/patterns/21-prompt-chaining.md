# Prompt Chaining

**Category:** Loop & Reasoning  
**Status:** Extended

## Intent

Decompose a complex task into a fixed sequence of LLM calls, where each call's output is the next call's input — making each step simple, specialized, and independently testable.

## When to use

- Tasks that benefit from specialization at each stage (draft → critique → rewrite → format → deliver)
- When a single prompt produces unreliable output because the task combines too many requirements
- Transformation pipelines: extract → normalize → enrich → summarize
- When different stages need different models, temperatures, or system prompts
- As the foundation for pipeline agents before adding dynamic routing

**Differs from ReAct** ([01-react-loop.md](01-react-loop.md)) in that prompt chaining is predetermined and linear — the sequence of calls is fixed at design time, not determined by LLM output at runtime.

## How it works

### Sequential chain

```
User input
     │
     ▼
LLM Call 1 (extraction)
  Output: structured data
     │
     ▼
LLM Call 2 (analysis)
  Output: analysis
     │
     ▼
LLM Call 3 (formatting)
  Output: final report
     │
     ▼
Response to user
```

### Parallel then merge

```
User input
     │
     ├──► LLM Call A (perspective 1) ──┐
     ├──► LLM Call B (perspective 2) ──┼──► LLM Call D (synthesis) ──► output
     └──► LLM Call C (perspective 3) ──┘
```

### Conditional chain

```
Input
  │
  ▼
LLM Call 1 (classify)
  │
  ├──(type A) ──► LLM Call 2a ──► output A
  └──(type B) ──► LLM Call 2b ──► output B
```

## Key design decisions

1. **Where to split** — split at each logical transformation, not arbitrarily. If a call does two different things, split it.
2. **What to pass forward** — pass only what the next step needs. Strip verbose intermediate content. Smaller context = lower cost and higher reliability.
3. **Where to validate** — add a validation step after any LLM call whose output feeds into a tool call or external action.
4. **Where to allow deviation** — if a step's output should influence which step runs next, that's a router (see [13-router.md](13-router.md)) or a ReAct loop, not a chain.

## Variants

| Variant | Description |
|---|---|
| **Gate-and-proceed** | After each step, check if a quality threshold is met before proceeding. If not, retry or raise an error. |
| **Windowed chain** | Each call receives only the last K steps' context, not the full chain history. Keeps context size bounded. |
| **Model cascade** | Start with a small/fast model; only escalate to a large/slow model if output quality is insufficient. |
| **Template chain** | Each step fills variables into a template, rather than generating free-form text. Extremely reliable for structured outputs. |

## Related patterns

- [07-chain-of-thought.md](07-chain-of-thought.md) — CoT is applied within a single call in the chain; chaining extends this across multiple calls
- [01-react-loop.md](01-react-loop.md) — ReAct is a dynamic chain where the LLM decides the next step; prompt chaining is a static chain decided by the engineer
- [13-router.md](13-router.md) — a conditional chain is a router; consider using the Router pattern explicitly when branching logic is complex
- [16-orchestrator-worker.md](16-orchestrator-worker.md) — a pipeline chain IS a sequential Orchestrator-Worker arrangement
- [11-llm-as-judge.md](11-llm-as-judge.md) — the gate-and-proceed variant uses LLM-as-Judge as the gating mechanism

## Implementation notes

- Name each step in the chain explicitly (e.g., `extract`, `analyze`, `format`) and log its input and output. Anonymous chains are impossible to debug.
- Pass intermediate outputs as typed data structures, not raw strings, where possible. A typed extraction makes it harder for downstream steps to silently misinterpret the previous step's output.
- Test each step independently before testing the full chain. A failure anywhere in the chain should be traceable to exactly one step.
- Chains with > 5 steps tend to compound errors — each step inherits and amplifies mistakes from previous steps. Consider introducing validation gates or splitting into parallel sub-chains for very long chains.
