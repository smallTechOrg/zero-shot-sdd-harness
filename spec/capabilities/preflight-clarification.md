# Capability: Pre-flight Clarification Check (C26)

## What It Does
Before running the agent, asks a clarifying question if the request is too ambiguous to answer well.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | `/ask` | yes |
| dataset schemas | JSON | DB | yes |
| skip_clarification | bool | `/ask` | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| clarification response | JSON | `{type:"clarification", clarification_question, run_id, session_id}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM via `LLMClient` (`<node:clarify>`) | decide proceed vs ask | on failure → proceed |

## Business Rules
- Skipped when explicit `dataset_ids` supplied or `skip_clarification=true`.
- A clarification returns early with a thin run (status `clarification`); no agent run.
- Stub always returns "proceed".

## Success Criteria
- [ ] An ambiguous question returns `type:"clarification"` with a question and a `clarification` run.
- [ ] Re-submitting with `skip_clarification:true` runs the agent and returns an answer.
- [ ] A clear question proceeds directly to an answer.
