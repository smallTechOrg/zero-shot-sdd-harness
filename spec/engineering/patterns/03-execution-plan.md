# Execution Plan

**Category:** Orchestration  
**Status:** Core — the LLM response format for all tool invocations

## Intent

The LLM responds with a structured YAML workflow (a state machine) that the agent runtime walks, rather than a single opaque instruction. This makes the agent's intentions explicit, inspectable, and executable in parallel or conditionally.

## When to use

- When a task requires calling multiple tools, potentially in parallel
- When different tool results should trigger different follow-up actions
- When the full reasoning path should be logged as a structured trace
- As the single LLM response mode (do not mix with unstructured prose tool calls)

## How it works

The LLM produces a YAML document. The plan executor walks the state graph, launching parallel branches concurrently, and routing on outcome via `on_success` / `on_error`.

### Canonical schema

```yaml
id: agent_market_and_travel_analyzer    # canonical name for this task
goal: "Analyze stock trends and flight prices simultaneously, then book if both align."
start: fork_research_tasks              # entry-point state

states:

  fork_research_tasks:
    type: parallel
    branches:
      - id: stock_analysis_branch
        start: fetch_market_data
        states:
          fetch_market_data:
            type: tool_call
            tool_name: stock_ticker_api
            capability_name: get_stock_ticker
            arguments: { ticker: "AAPL" }
            on_success: branch_complete
            on_error:                   # empty = propagate to workflow default

      - id: travel_analysis_branch
        start: fetch_flight_data
        states:
          fetch_flight_data:
            type: tool_call
            tool_name: flight_price_api
            capability_name: get_flight_price
            arguments: { destination: "SFO" }
            on_success: branch_complete
            on_error: abort_workflow

    join:
      strategy: all   # "all" = wait for every branch; "race" = first-wins
      next: evaluate_combined_metrics

  evaluate_combined_metrics:
    type: reasoning
    instructions: "Look at stock trend from stock_analysis_branch and flight price. Make a booking decision."
    on_success: execute_action

  execute_action:
    type: switch
    expression: "context.stock_analysis_branch.last_output.trend == 'bullish' && context.travel_analysis_branch.last_output.price < 400"
    cases:
      true:  complete_workflow
      false: abort_workflow
    on_error: abort_workflow

  complete_workflow:
    type: end
    status: success

  abort_workflow:
    type: end
    status: failed
    reason: "Market conditions or flight prices did not meet optimization thresholds."
```

## Top-level fields

| Field | Description |
|---|---|
| `id` | Canonical name for this task instance |
| `goal` | The objective as understood by the LLM |
| `start` | Name of the entry-point state |
| `states` | Map of state name → state definition |

## State types

| Type | Key fields | Description |
|---|---|---|
| `tool_call` | `tool_name`, `capability_name`, `arguments`, `on_success`, `on_error` | Invoke a tool capability; route on outcome |
| `parallel` | `branches[]` (`id`, `start`, `states`), `join` (`strategy`, `next`) | Fork concurrent branches; join by `all` or `race` |
| `reasoning` | `instructions`, `on_success` | Pass accumulated context back to the LLM for a reasoning step |
| `switch` | `expression`, `cases`, `on_error` | Route based on an expression over `context` |
| `end` | `status`, `reason` (optional) | Terminal state — `success` or `failed` |

`on_error` is optional on any state. An absent `on_error` propagates the failure to the nearest enclosing parallel branch or the workflow default error handler.

## Plan executor responsibilities

1. **`tool_call` states:** Resolve tool by `tool_name` from registry; call `capability_name` with `arguments`; route via `on_success` or `on_error`.
2. **`parallel` states:** Launch all branches as concurrent tasks; hold at join point until join strategy is satisfied (`all` = every branch completes, `race` = first to complete wins).
3. **`reasoning` states:** Assemble accumulated `context` from all completed branches; call `plan_action` for a follow-up reasoning step.
4. **`switch` states:** Evaluate `expression` against `context`; route to the matching case.
5. **`end` states:** Record final status and terminate the plan.

Branch outputs are accessible in `switch` and `reasoning` states via `context.<branch_id>.last_output`.

## Related patterns

- [01-react-loop.md](01-react-loop.md) — the `plan_action` node produces the execution plan; `invoke_tool` walks it
- [02-tool-registry.md](02-tool-registry.md) — `tool_name` references are resolved against the registry
- [04-sub-agent-as-tool.md](04-sub-agent-as-tool.md) — sub-agent invocations appear as `tool_call` states
- [05-self-correction.md](05-self-correction.md) — failed `tool_call` states trigger self-correction before `on_error`
- [22-observability.md](22-observability.md) — the plan structure is the primary unit of observability trace

## Implementation notes

- Validate the plan schema immediately after LLM response, before executing any state. If validation fails, treat it as a recoverable error and ask the LLM to reformat.
- Every executed state is appended to `tool_call_history` so the reasoning trace is complete.
- The `reasoning` state is not a tool call — it incurs another LLM call. Limit consecutive `reasoning` states to avoid runaway LLM costs.
- Keep branch `id` values short and meaningful — they are used as keys in `context` and appear in logs.
- Sub-agent tools are invoked via `tool_call` states identically to any other tool. The plan executor is unaware of whether a tool is an API wrapper or a child agent.
