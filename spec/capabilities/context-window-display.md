# Capability: Live Context-window Display (C29)

## What It Does
Shows a token-budget estimate at rest and a per-component prompt breakdown after each run.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| datasets/memory/history sizes | derived | DB | yes |
| prompt_breakdown | JSON | `/ask` response | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| sidebar budget bar + breakdown | UI | Analyse sidebar / turn |

## External Calls
None.

## Business Rules
- `prompt_breakdown` components: `system_overhead`, `dataset_schemas`, `history`, `memory`, `dataset_notes`, `action_history`, `total_prompt`.
- At-rest bar estimates context fill before a run from datasets + memory.

## Success Criteria
- [ ] After a run, `prompt_breakdown` includes all named components and `total_prompt` ≈ their sum.
- [ ] The sidebar budget bar renders a non-zero estimate when datasets/memory exist.
