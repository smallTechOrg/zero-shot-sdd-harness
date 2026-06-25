# Capability: Early Exit / Force-finalize (C20)

## What It Does
Guarantees the agent always returns a best-effort answer by synthesizing one when it hits max iterations or repeated errors.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| action_history | list | state | yes |
| iteration_count / consecutive errors | int | state | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| best-effort answer | string | `query_runs.answer`; `is_best_effort=true` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM via `LLMClient` (`<node:finalize>`) | one synthesis call | fall back to static message |

## Business Rules
- Fires on max-iter OR 3 consecutive `is_error` steps.
- `status` is ALWAYS `completed`; `error_message` = `max_iterations` or `consecutive_errors` (informational).
- A failed synthesis call falls back to a static best-effort message.

## Success Criteria
- [ ] A run that hits `max_iterations` returns `status=completed`, `is_best_effort=true`, and a non-empty answer.
- [ ] Three consecutive execution errors force-finalize rather than failing the run.
