# Self-Correction

**Category:** Evaluation & Quality  
**Status:** Core — required in any ReAct loop that calls external tools

## Intent

When a tool call fails with a recoverable error, feed the failure back to the LLM with an explanation rather than immediately terminating the run. Let the LLM diagnose and correct its mistake.

## When to use

Any time a tool call produces an error that the LLM could fix if it had better information — a typo in a parameter, a wrong capability name, a malformed value. Only escalate to fatal when the environment itself is broken.

## How it works

```
invoke_tool
     │
     ├──(success) ─────────────────────────────────► next state in plan
     │
     ├──(recoverable error) ─► append to tool_call_history (is_error=True)
     │                         increment iteration_count
     │                         ──► plan_action (with error inline in prompt)
     │
     └──(fatal error) ────────────────────────────► handle_error → END
```

On the next `plan_action` call, the prompt includes the failed call and its error:

```
[2] Tool: weather_api | Capability: get_forecast | Parameters: {"city": "Londn"}
    Error: City not found. Check the spelling and try again.
    → This tool call failed. Correct it and try again.
```

The LLM reads the error, diagnoses the cause, and produces a corrected execution plan.

## Recoverable errors — feed back and loop

| Error type | Example |
|---|---|
| Tool execution error | `4xx` from a provider API |
| Bad parameter value | City name misspelled, date out of range |
| Malformed LLM response | Non-JSON output, missing required fields |
| Unknown capability name | LLM invents a capability that doesn't exist |
| Parameter validation failure | Wrong type, missing required field |

For all of these: append to `tool_call_history`, increment `iteration_count`, route back to `plan_action`.

## Fatal errors — route to `handle_error` immediately

| Error type | Example |
|---|---|
| Max iterations reached | `iteration_count >= max_iterations` |
| LLM call fails | Network error, `5xx` from LLM provider |
| Infrastructure failure | Provider unreachable, credentials revoked |
| Irrecoverable executor error | Sandbox crash, disk full |

Fatal errors are environment failures, not reasoning failures. The LLM cannot fix them by trying again.

## Key principle

> If the LLM could correct the mistake given better information, feed back and loop. Only fail when the environment itself is broken.

## `tool_call_history` schema

```python
class ToolCallRecord(TypedDict):
    tool: str          # tool_name
    capability: str    # capability_name
    parameters: dict   # arguments passed
    result: str        # response from tool (or error message)
    is_error: bool     # True if this call failed
```

Persist `tool_call_history` to the database as JSON so it can be surfaced in the UI as an agent reasoning trace.

## Variants

| Variant | Description |
|---|---|
| **Single retry** | Feed back once; if the corrected call also fails, treat as fatal |
| **Progressive hints** | On repeated failure of the same tool, add progressively more explicit guidance in the prompt (e.g., "the city parameter requires the English name, not the local name") |
| **Alternative path** | After N failures on one tool, instruct the LLM to try a different tool for the same goal |

## Related patterns

- [01-react-loop.md](01-react-loop.md) — self-correction is the `tool_error` branch of the loop
- [03-execution-plan.md](03-execution-plan.md) — `on_error` transitions in execution plans route to or bypass self-correction
- [11-llm-as-judge.md](11-llm-as-judge.md) — a complementary quality pattern that evaluates outputs, not just execution errors
- [23-constitutional-ai.md](23-constitutional-ai.md) — principle-based self-evaluation, distinct from error-based self-correction

## Implementation notes

- Format the error block in `tool_call_history` the same way every time — the LLM must learn to recognize "→ This tool call failed" as a cue to correct.
- Include the full parameter dict in the error block, not just the error message. The LLM needs to see what it sent to know what to change.
- When the LLM produces a malformed execution plan, treat it as recoverable: show the parse error and the schema, ask it to reformat. Only mark fatal after 3 consecutive malformed responses.
- The iteration ceiling is the safety net for self-correction loops. Set it thoughtfully: too low and the agent cannot self-correct complex errors; too high and a confused agent burns tokens.
