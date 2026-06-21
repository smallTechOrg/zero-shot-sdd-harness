# Sub-agent as Tool

**Category:** Orchestration  
**Status:** Core — the primary mechanism for hierarchical agent architectures

## Intent

Register a child AI agent as a tool in the parent agent's Tool Registry, so the master agent can delegate scoped sub-problems to specialist agents without special orchestration code — just a tool call.

## When to use

- When a task has distinct sub-problems that require different domain expertise
- When a sub-problem is complex enough to warrant its own ReAct loop and tool set
- When you want to parallelize: master spawns multiple specialist agents in parallel branches
- When the master agent should not need to understand the internal mechanics of a sub-problem

## How it works

The master agent calls a sub-agent tool exactly like any other tool, by naming it and passing a prompt:

```json
{
  "tool_name": "market_analyst_agent",
  "capability_name": "analyze",
  "arguments": { "prompt": "What is the 30-day trend for AAPL?" }
}
```

The sub-agent tool:
1. Receives the prompt (and optionally structured context from the parent's state)
2. Runs its own internal ReAct loop — which may itself call tools or spawn further sub-agents
3. Returns a response string (or structured JSON) to the parent agent
4. Is **opaque** to the parent: the parent sees a result, not the sub-agent's internal reasoning

This enables hierarchical agent architectures:

```
Master agent
  ├── invoke_tool("market_analyst_agent", prompt) → runs own loop → returns analysis
  ├── invoke_tool("travel_agent", prompt)         → runs own loop → returns recommendation
  └── FINAL ANSWER: <combined decision using both results>
```

### Registration

Register sub-agents in the Tool Registry the same way as any other tool:

```
Tool record
  ├── name:        "market_analyst_agent"
  ├── type:        "sub_agent"
  ├── description: "Specialist agent for equity market analysis."
  └── capabilities:
        └── analyze
              description: "Analyze a market question and return a recommendation."
              parameter_schema:
                prompt: { type: string, required: true }
                context: { type: object, required: false }
```

## Key components

1. **Tool Registry entry** — sub-agent registered as category `Orchestration`, type `sub_agent`
2. **Capability schema** — at minimum a `prompt` field; optionally structured `context` fields from parent state
3. **Sub-agent executor** — the `invoke_tool` dispatcher that instantiates the child agent, runs it, and returns its result
4. **Isolation** — child agent runs with its own state, its own tool set, and its own iteration ceiling

## Variants

| Variant | Description |
|---|---|
| **Parallel specialists** | Master spawns N sub-agents in a `parallel` execution plan state; all run concurrently |
| **Sequential refinement** | Master chains sub-agents: output of agent A feeds as prompt context to agent B |
| **Recursive delegation** | Sub-agent itself spawns further sub-agents; creates a tree of agents |
| **Scoped tool set** | Each sub-agent is registered with a different subset of available tools (research agent sees only read tools; action agent sees only write tools) |

## Related patterns

- [01-react-loop.md](01-react-loop.md) — each sub-agent runs its own ReAct loop
- [02-tool-registry.md](02-tool-registry.md) — sub-agents registered under `Orchestration` category
- [03-execution-plan.md](03-execution-plan.md) — sub-agent calls appear as `tool_call` states in the execution plan
- [16-orchestrator-worker.md](16-orchestrator-worker.md) — Orchestrator-Worker is the architectural level above this pattern (the master agent IS the orchestrator)

## Implementation notes

- The master agent's `tool_call_history` records the sub-agent invocation and its result. It does not record the sub-agent's internal `tool_call_history` — those live in the child run's DB record.
- Sub-agent tool calls count against the master agent's `iteration_count`. Each sub-agent invocation is one iteration from the master's perspective, regardless of how many iterations the child took.
- Set an independent `max_iterations` for each sub-agent level. Deeply nested hierarchies can compound iteration ceilings.
- If a sub-agent returns an error, treat it as a tool error and apply the standard self-correction flow — see [05-self-correction.md](05-self-correction.md).
- For production systems, consider a maximum depth limit on agent nesting (e.g., 3 levels) to prevent unbounded recursion.
