# Orchestrator-Worker

**Category:** Orchestration  
**Status:** Extended

## Intent

A master orchestrator agent delegates subtasks to specialist worker agents or functions — coordinating their execution, aggregating their results, and synthesizing a final output. Workers are scoped, focused, and unaware of the broader task.

## When to use

- Tasks that decompose naturally into independent or semi-independent subtasks
- When subtasks are best handled by specialists with different tools, prompts, or models
- When parallel execution of subtasks is desirable for throughput
- When task complexity exceeds what a single ReAct loop can handle reliably at scale

**Differs from Sub-agent as Tool** ([04-sub-agent-as-tool.md](04-sub-agent-as-tool.md)) in that the orchestrator has *intentional awareness* of the worker topology — it explicitly knows it is coordinating N workers. Sub-agent as Tool treats workers as opaque tool calls.

## How it works

### Fan-Out / Fan-In

```
Orchestrator
  │
  ├──► Worker A (process chunk 1)
  ├──► Worker B (process chunk 2)
  ├──► Worker C (process chunk 3)
  │
  └──[join when all complete]
          │
          ▼
     Aggregator / Synthesizer
          │
          ▼
     Final result
```

### Map-Reduce

```
Orchestrator
  │
  ├──[map] distribute data shards to N workers
  │    ├── Worker 1: summarize doc chunk 1
  │    ├── Worker 2: summarize doc chunk 2
  │    └── Worker N: summarize doc chunk N
  │
  └──[reduce] synthesize N partial summaries into one final summary
```

### Pipeline (Sequential)

```
Orchestrator
  │
  ▼
Worker A (research)
  │  output →
Worker B (analysis)
  │  output →
Worker C (report generation)
  │
  ▼
Final report
```

Each worker's output becomes the next worker's input.

## Worker design

Workers should be:
- **Scoped** — given only the tools and context they need for their subtask
- **Stateless** — receive their full input on invocation; do not depend on shared mutable state
- **Self-contained** — can be tested independently without the orchestrator
- **Single-responsibility** — one worker = one type of task

## Variants

| Variant | Description |
|---|---|
| **Fan-Out / Fan-In** | N workers in parallel, one aggregator. Best for independent parallel tasks. |
| **Map-Reduce** | Fan-out with structured aggregation. Best for processing large datasets. |
| **Pipeline** | Sequential workers. Best when each step transforms the output for the next. |
| **Dynamic dispatch** | Orchestrator decides at runtime which workers to call and in what order (converges with [13-router.md](13-router.md)). |
| **Competing workers** | N workers attempt the same task; the best result wins (converges with [12-self-consistency.md](12-self-consistency.md)). |
| **Supervisor-Reviewer** | After workers complete, a separate Reviewer worker evaluates and requests corrections before the final result is accepted. |

## Related patterns

- [04-sub-agent-as-tool.md](04-sub-agent-as-tool.md) — the worker implementation: each worker is a sub-agent
- [03-execution-plan.md](03-execution-plan.md) — the execution plan's `parallel` state type models fan-out/fan-in
- [13-router.md](13-router.md) — orchestrator routing logic is a form of intent routing
- [12-self-consistency.md](12-self-consistency.md) — competing workers pattern IS Best-of-N
- [11-llm-as-judge.md](11-llm-as-judge.md) — the Supervisor-Reviewer variant uses LLM-as-Judge

## Implementation notes

- Design the orchestrator to be recoverable: if one worker fails, should the whole run fail or continue with partial results? Specify this per-task in the spec.
- Pass only the necessary context to each worker. Sending the full orchestrator state to every worker increases cost and may expose data the worker should not see.
- For fan-out, set a reasonable cap on the number of parallel workers per run (e.g., max 10). Unbounded fan-out at high concurrency stresses rate limits and database connections.
- Workers that call the same external API concurrently may hit rate limits. Build rate-limit-aware scheduling into the orchestrator or use a shared rate limiter.
- Track worker results in the orchestrator's state — not just the final aggregation. This enables debugging individual worker outputs when the aggregated result is wrong.
