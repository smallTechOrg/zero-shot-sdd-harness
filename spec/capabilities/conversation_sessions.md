# Capability: Conversation Sessions

## What It Does
Keeps a dataset "loaded" across many questions and remembers the conversation, so follow-up questions that reference prior turns ("now break that down by region", "just the top one") resolve correctly without repeating context.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | str | session creation | yes |
| session_id | str | `POST /runs` body (Phase 2) | no (created on first question) |
| question | str | `POST /runs` body | yes |
| prior turns | list[{question, answer}] | `runs` in the session (threaded into state `messages`) | yes for follow-ups |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Session row | DB record (`sessions`) | SQLite |
| Run linked to session | `runs.session_id` set | SQLite |
| Context-aware answer | run result | API + UI chat thread |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`generate_code`, `write_answer`) | Same as analyze_dataset, now with prior-turn context in the prompt | Fatal — run `failed` (unchanged from Phase 1) |

## Business Rules
- Conversation history is threaded into the `generate_code`/`write_answer` prompts via the state `messages` field; capped to the last N turns to bound prompt size.
- Only prior **questions and aggregated answers** enter the prompt as memory — never raw rows.
- A session is scoped to exactly one dataset; a new dataset starts a new session.
- Follow-ups reuse the loaded dataset's profile/context without re-profiling.

## Success Criteria
- [ ] Asking a question, then a follow-up that omits the subject ("now by month") returns an answer that correctly builds on the previous turn's result.
- [ ] The follow-up run is linked to the same `session_id` as the first.
- [ ] Prompt memory is capped (an N+1-turn session does not send unbounded history).
- [ ] Starting a session on a different dataset does not leak the prior dataset's turns.
