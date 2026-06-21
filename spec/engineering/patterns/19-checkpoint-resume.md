# Checkpoint / Resume

**Category:** Memory  
**Status:** Extended

## Intent

Persist agent state to durable storage at regular intervals so a long-running agent can resume from its last checkpoint after a failure, restart, or timeout — without re-executing completed steps.

## When to use

- Agent runs that take longer than a few minutes (risk of process restart, timeout, or infra failure)
- Agents that make expensive or irreversible tool calls (do not re-run a payment or email tool from scratch)
- Agents with many tool-call iterations (> 20) where restarting from scratch is prohibitively costly
- Event-driven agents that must survive worker process restarts (see [18-event-driven-agent.md](18-event-driven-agent.md))
- Human-in-the-loop flows where the agent may be paused for hours waiting for approval (see [15-human-in-the-loop.md](15-human-in-the-loop.md))

## How it works

```
plan_action ──► invoke_tool ──► [write checkpoint] ──► plan_action ──► ...
                                        │
                                        ▼
                                  DB: run record
                                    - current_state_id
                                    - agent_state (JSON)
                                    - tool_call_history (JSON)
                                    - iteration_count
                                    - checkpoint_at

                                  (on process restart or failure)
                                        │
                                        ▼
                                  Load checkpoint from DB
                                  Resume from current_state_id
```

## What to checkpoint

| Field | Why |
|---|---|
| `current_state_id` | Which state in the execution plan to resume from |
| `agent_state` | Full `AgentState` — all fields, serialized as JSON |
| `tool_call_history` | Every call that has already been made |
| `iteration_count` | Prevent double-counting against `max_iterations` |
| `checkpoint_at` | Timestamp — for debugging and audit |

Do not checkpoint intermediate tool call results that are already captured in `tool_call_history`.

## Checkpoint frequency

| Run type | Recommended frequency |
|---|---|
| Fast runs (< 2 min) | No checkpoint needed — restart from scratch |
| Medium runs (2–10 min) | After every tool call |
| Long runs (> 10 min) | After every tool call; also before any irreversible action |
| HITL flows | Always checkpoint before the approval pause |

## LangGraph native support

LangGraph provides built-in checkpointers:

```python
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.postgres import PostgresSaver

# Development
memory = SqliteSaver.from_conn_string(":memory:")

# Production
memory = PostgresSaver.from_conn_string(DATABASE_URL)

# Wire into graph
compiled_graph = graph.compile(checkpointer=memory)
```

Each graph invocation is assigned a `thread_id`. Resuming is:

```python
config = {"configurable": {"thread_id": run_id}}
result = await compiled_graph.ainvoke(initial_state, config=config)
# On restart, compiled_graph.ainvoke with the same thread_id resumes from checkpoint
```

## Variants

| Variant | Description |
|---|---|
| **After-every-step** | Checkpoint after every state in the execution plan. Safest; highest write overhead. |
| **Before-irreversible** | Checkpoint only before irreversible actions (email, payment). Efficient; coverage depends on correct tagging. |
| **Periodic** | Checkpoint every N seconds or N iterations. Simple to implement. |
| **On-pause** | Checkpoint only when the agent is explicitly paused (HITL gate, scheduled stop). |

## Related patterns

- [01-react-loop.md](01-react-loop.md) — checkpoint after each iteration of the ReAct loop
- [15-human-in-the-loop.md](15-human-in-the-loop.md) — HITL approval gates require checkpointing: the agent persists state and resumes when approval arrives
- [18-event-driven-agent.md](18-event-driven-agent.md) — event-driven agents need checkpointing to survive worker restarts
- [09-memory-patterns.md](09-memory-patterns.md) — checkpointing is persistence of working memory

## Implementation notes

- Checkpoint writes must be atomic — partial writes corrupt the resume state. Use transactions or a single JSON field write.
- Include a `schema_version` field in the checkpoint JSON. When `AgentState` fields change, the loader can detect stale checkpoints and fail gracefully rather than loading corrupted state.
- Test the resume path explicitly in integration tests: start a run, simulate a failure mid-run, restart, verify it completes correctly without re-executing completed steps.
- Expired or abandoned checkpoints accumulate over time. Add a cleanup job that deletes checkpoints for runs older than a retention period (e.g., 30 days).
- Never checkpoint credentials or PII in the agent state JSON without appropriate at-rest encryption.
