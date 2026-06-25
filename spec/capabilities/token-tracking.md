# Capability: Per-run Token Tracking (C7)

## What It Does
Accumulates input/output token counts across every LLM call in a run and persists them.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| LLM responses | provider usage | each LLM call | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| tokens_input, tokens_output | int | `query_runs` row + `/ask` response |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM provider | report usage | if unavailable, estimate or 0; never crash |

## Business Rules
- Token counts accumulate across `plan_action`, `force_finalize`, and graph-adjacent calls (selector/clarify/suggest) for the same run.
- Stub mode reports plausible/zero counts without error.

## Success Criteria
- [ ] After a multi-iteration run against real Gemini, `tokens_input` and `tokens_output` are > 0 and persisted.
- [ ] The `/ask` response carries the same totals as the `query_runs` row.
