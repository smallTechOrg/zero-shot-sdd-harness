# Capability: Conversational Memory (Phase 2 — deferred)

## What It Does
Carries conversation context across turns so follow-ups like "now break that down by region" resolve against the prior question and dataset without restating them.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | query request | yes |
| messages | list | persisted session history | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| updated messages | list | `sessions` history |
| context-aware plan/code | str | plan/generate_code nodes |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | plan with prior turns | retry/backoff → error |

## Business Rules
- History stored per session; truncated to last N turns + rolling summary to fit context.
- History contains questions/answers/summaries only — never raw rows.

## Success Criteria
- [ ] A follow-up referencing "that" resolves to the previous result's grouping.
- [ ] History persists across restart and reloads into the session.
