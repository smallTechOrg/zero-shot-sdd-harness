# Capability: Follow-up Conversation (Phase 2 — stub in Phase 1)

## What It Does
Lets the user ask many follow-up questions against the loaded dataset within a session, each seeing prior turns (conversation memory) — without raw rows ever entering the prompt.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | path | yes |
| question | string | ask body | yes |
| conversation_id | string | session | yes (created on first ask) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer (context-aware) | same as [answer-question-with-code](answer-question-with-code.md) | SSE + `questions` row linked by `conversation_id` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | code-gen prompt now includes prior-turn **summaries** (question + answer text), never raw rows | falls back to single-turn behaviour |

## Business Rules
- Memory is short-term (within-session) prior-turn summaries injected into the code-gen context — pattern #8. Cross-day persistence is Phase 3.
- Prior-turn content is the question text + answer summary + result shape — **never** raw rows. The privacy boundary holds across turns.
- A follow-up like "now break that down by month" must resolve against the previous question's subject.

## Success Criteria
- [ ] **Multi-interaction:** ask, then ask a follow-up that references the first answer in the same session; the second response uses the first's context (assert it, not just non-empty).
- [ ] No raw row value appears in any prompt across multiple turns.
- [ ] Each turn is persisted with its `conversation_id`.
