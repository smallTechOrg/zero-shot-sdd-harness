# Capability: Expanded Result Display (C8)

## What It Does
Lets the agent show large intermediate results (up to ~100 rows / 20 cols) without truncating to pandas defaults.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| action result | pandas object | execute_action | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| stringified result | string | `action_history[].result` |

## External Calls
None.

## Business Rules
- pandas display options widened (≈100 rows, 20 cols) when stringifying results in the sandbox so the model and the Steps inspector see useful output.
- Very large results are still bounded to avoid runaway prompts.

## Success Criteria
- [ ] A `df.head(100)` style result is captured with up to ~100 rows visible in the step result, not truncated to 5/10.
- [ ] A wide frame shows up to ~20 columns.
