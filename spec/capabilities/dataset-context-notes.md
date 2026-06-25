# Capability: Dataset Context Notes Injection (C12)

## What It Does
Injects each dataset's context notes (and column schema) into the agent prompt so answers are grounded in domain context.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset.context / context_facts | text / JSON | `datasets` row | no |
| column schema | JSON | `datasets.columns_json` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_context | string | `AgentState.dataset_context` → `plan_action` prompt |

## External Calls
None (read from DB).

## Business Rules
- Context ≤ 4000 chars; editable via `PATCH /datasets/{id}/context`.
- Both user notes and C31 compressed facts may contribute; column schema always included.

## Success Criteria
- [ ] A dataset with a context note has that note present in the assembled `plan_action` prompt (verifiable via `prompt_breakdown.dataset_notes` > 0).
- [ ] Editing the context via PATCH changes the injected text on the next run.
