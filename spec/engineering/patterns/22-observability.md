# Observability / Tracing

**Category:** Observability  
**Status:** Extended

## Intent

Emit structured trace events for every significant agent operation — LLM calls, tool invocations, routing decisions, errors — so that any run can be fully reconstructed, debugged, and audited after the fact.

## When to use

- All production agents — observability is not optional in deployed systems
- Any time you need to answer "why did the agent do X?" or "where did it go wrong?"
- When SLA, latency, or cost metrics must be monitored
- Compliance contexts where an audit trail of every action is required

## What to trace

Every trace event should include:

| Field | Description |
|---|---|
| `run_id` | The unique identifier for this agent run |
| `event_type` | `llm_call`, `tool_call`, `routing_decision`, `error`, `checkpoint`, `hitl_pause` |
| `timestamp` | ISO 8601 with millisecond precision |
| `node_name` | Which node or step in the execution plan |
| `input` | Prompt sent to LLM (truncated at 2000 chars), or tool arguments |
| `output` | LLM response or tool result (truncated at 2000 chars) |
| `latency_ms` | Wall-clock time for the operation |
| `token_count` | Input + output tokens (LLM calls only) |
| `model` | LLM model name (LLM calls only) |
| `error` | Error message if the operation failed |
| `is_error` | Boolean flag |
| `metadata` | Dict of additional context (tool_name, capability_name, user_id, session_id, etc.) |

## Trace hierarchy

A run produces a tree of events:

```
Run run_id=abc123
  ├── Event: llm_call (plan_action iteration 1)
  │     ├── input: system prompt + user query + tool list
  │     └── output: execution plan YAML
  ├── Event: tool_call (invoke_tool: weather_api.get_forecast)
  │     ├── input: { city: "London", days: 3 }
  │     └── output: { temperature: 18, condition: "cloudy" }
  ├── Event: llm_call (plan_action iteration 2)
  │     ├── input: [full context with tool_call_history]
  │     └── output: FINAL ANSWER: It will be 18°C and cloudy in London.
  └── Event: run_complete
        └── final_answer: "It will be 18°C and cloudy in London."
```

## Storage and query

### Minimum viable: DB table

```sql
CREATE TABLE trace_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      UUID NOT NULL REFERENCES runs(id),
    event_type  TEXT NOT NULL,
    node_name   TEXT,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
    input_text  TEXT,
    output_text TEXT,
    latency_ms  INTEGER,
    token_count INTEGER,
    model       TEXT,
    error       TEXT,
    is_error    BOOLEAN NOT NULL DEFAULT FALSE,
    metadata    JSONB
);

CREATE INDEX ON trace_events (run_id);
CREATE INDEX ON trace_events (event_type, timestamp);
```

### Advanced: dedicated tracing backends

| Tool | Description |
|---|---|
| **LangSmith** | Purpose-built for LLM traces; first-class LangChain/LangGraph support |
| **OpenTelemetry** | Open standard; export to Jaeger, Zipkin, Grafana Tempo, Honeycomb |
| **Weights & Biases Weave** | AI-specific; supports evaluation and regression tracking |
| **Arize Phoenix** | LLM observability with built-in evaluation and drift detection |
| **Langfuse** | Open-source LLM observability; self-hostable |

## Cost and latency monitoring

Aggregate trace events to compute per-run and fleet-wide metrics:

| Metric | Description |
|---|---|
| `total_llm_calls` | Number of LLM calls per run |
| `total_tool_calls` | Number of tool invocations per run |
| `total_tokens` | Sum of input + output tokens per run |
| `total_cost_usd` | Estimated cost based on model pricing |
| `p50_latency_ms` | Median end-to-end run latency |
| `error_rate` | % of runs ending with status `failed` |
| `iteration_distribution` | Histogram of `iteration_count` values across runs |

## Variants

| Variant | Description |
|---|---|
| **Inline tracing** | Write trace events synchronously in each node. Simple; adds latency. |
| **Async tracing** | Emit events to a queue; a background consumer writes to the trace store. No latency impact; risk of lost events on crash. |
| **Sampling** | Trace 100% of errors; sample 10% of successes. Reduces volume for high-throughput agents. |
| **Redacted tracing** | Apply PII redaction to all trace content before writing. Required in regulated domains. |

## Related patterns

- [01-react-loop.md](01-react-loop.md) — every iteration of the loop emits trace events
- [05-self-correction.md](05-self-correction.md) — self-correction events are a critical subset of traces (show the agent correcting mistakes)
- [09-memory-patterns.md](09-memory-patterns.md) — episodic memory IS the trace store; the reasoning trace shown in the UI is the trace
- [22-observability.md](22-observability.md) — `tool_call_history` in `AgentState` is the in-memory trace; persisting it to DB makes it observability

## Implementation notes

- Instrument before going to Phase 3. Trying to add observability to a running production agent is much harder than building it in from the start.
- Never log the full LLM prompt without a length limit — prompts with RAG context can be tens of thousands of tokens. Truncate at 2000 chars; store the full version in a separate `prompt_store` table if needed.
- Use a consistent `run_id` throughout a run and propagate it across all sub-agent calls. Without a common run_id, tracing through a hierarchical agent tree is impossible.
- Trace the cost of every LLM call, not just the latency. Cost surprises in production are the #1 operational issue for LLM applications.
- Implement a "replay from trace" capability for debugging: given a `run_id`, reconstruct the exact prompt, tool results, and state at each step.
