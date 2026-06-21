# ReAct Loop

**Category:** Loop & Reasoning  
**Status:** Core — required for any agent that touches an external provider

## Intent

Interleave reasoning and action: the LLM plans a tool call, the harness executes it, the result is fed back, the LLM re-evaluates — repeating until a final answer emerges.

## When to use

Use a ReAct loop whenever the agent must interact with **any external provider**:

- Data providers: databases, CSV files, search indices, vector stores
- Service providers: REST APIs, GraphQL endpoints, email, messaging, calendar, CRM
- Compute providers: code execution, image generation, web scraping

**Do not** build a single-shot pipeline (one prompt → one LLM call → done) for tasks that need external data. Single-shot pipelines cannot chain dependent calls, cannot retry on failure, and cannot self-correct.

## How it works

Tool loading and session setup happen **before** the loop — they are not nodes in the loop graph.

```
[pre-loop: register tools, load session context into AgentState]
          │
          ▼
plan_action ◄──────────────────────────────────────┐
  │                                                │
  ├──(LLM failure) ──────► handle_error            │
  │                                                │
  ├──(FINAL ANSWER signal) ─► finalize ──► END     │
  │                                                │
  └──(execution plan) ───────► invoke_tool ─────────┘
                                  │
                                  ├──(fatal: infra failure) ─► handle_error
                                  │
                                  └──(tool error) ─► plan_action (self-correction)
```

`invoke_tool` is the **single dispatch point** for all external interactions. See [05-self-correction.md](05-self-correction.md) and [02-tool-registry.md](02-tool-registry.md).

## Key components

1. **`plan_action` node** — calls the LLM with: user goal, tool list, tool_call_history, and the execution plan schema. Parses the response and routes.
2. **`invoke_tool` node** — resolves tool from registry, calls capability, appends result to `tool_call_history`.
3. **`handle_error` node** — records failure, sets run status to `failed`, terminates.
4. **`finalize` node** — extracts the final answer from the FINAL ANSWER signal, persists to DB.

## Termination protocol (mandatory)

The LLM must have an unambiguous way to signal completion. Define this string in the spec:

```
FINAL ANSWER: <the complete answer text here>
```

`plan_action` checks if the LLM response contains `FINAL ANSWER:` (case-insensitive). If yes, strip the prefix and route to `finalize`. If no, parse as an execution plan and route to `invoke_tool`.

This is not optional — without a termination signal, the loop runs until the iteration ceiling.

## Max iterations guard (mandatory)

Every ReAct loop must have a configurable ceiling:

```python
max_agent_iterations: int = Field(default=10)
```

After each `invoke_tool`, increment `iteration_count`. If `iteration_count >= max_iterations`, route to `handle_error`. Never let a loop run unboundedly.

## Variants

| Variant | Description |
|---|---|
| **Single-tool ReAct** | Loop where every iteration calls the same tool (e.g., paginated search) |
| **Execution plan ReAct** | LLM responds with a full workflow YAML rather than a single tool call — see [03-execution-plan.md](03-execution-plan.md) |
| **Hierarchical ReAct** | `invoke_tool` calls a sub-agent which itself runs a ReAct loop — see [04-sub-agent-as-tool.md](04-sub-agent-as-tool.md) |

## Related patterns

- [02-tool-registry.md](02-tool-registry.md) — how tools are loaded into the loop
- [03-execution-plan.md](03-execution-plan.md) — what the LLM produces in `plan_action`
- [05-self-correction.md](05-self-correction.md) — what happens on `tool_error`
- [09-memory-patterns.md](09-memory-patterns.md) — how `tool_call_history` relates to working memory

## Implementation notes

- `tool_call_history` must be passed on **every** `plan_action` call so the LLM sees what was already tried.
- The `FINAL ANSWER` check must happen before attempting to parse the execution plan — the LLM may occasionally include plan syntax in the final-answer block.
- Phase 2 stub requirement: the stub must simulate at least two iterations — one that calls a tool and one that emits FINAL ANSWER. A stub that returns a final answer on the first call hides loop defects.
