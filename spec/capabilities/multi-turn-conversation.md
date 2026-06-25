# Capability: Multi-turn Conversation History (C3)

## What It Does
Carries prior turns into a session so follow-up questions see earlier context.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | string | `/ask` body | yes (for multi-turn) |
| prior turns | rows | `query_runs` by session | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| conversation_history | list | `AgentState` → `plan_action` prompt |

## External Calls
None (read from DB).

## Business Rules
- A session is capped at 20 turns (>20 → 400).
- Prior `{question, answer}` pairs are loaded into `conversation_history` for the run.

## Success Criteria
- [ ] Q1 then a context-dependent Q2 in the same session yields a Q2 answer that reflects Q1 (real Gemini).
- [ ] A 21st turn in a session returns 400.
