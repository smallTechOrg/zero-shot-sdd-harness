# Capability: Dataset Library + Resumable Sessions  *(Phase 3)*

## What It Does
Persists uploaded datasets into a browsable library the user returns to across days, and remembers conversation history + the active dataset in a resumable session.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| (none new) | — | existing Dataset/Run rows | — |
| session_id | string | path param (resume) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset list | json | `GET /datasets` |
| session + history | json | Session.messages_json, `GET /sessions/{id}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | list datasets, persist/load session messages | surfaced as api_error |
| Gemini | answer follow-up using prior turns as context | run fails gracefully |

## Business Rules
- Chat history (`AgentState.messages`) is persisted per session and reloaded on resume, so follow-ups respect prior turns.
- Conversation memory is the default for the chat surface — not optional.

## Success Criteria
- [ ] Datasets uploaded across visits all appear in `GET /datasets`.
- [ ] Reopening a session restores its prior turns + active dataset; a follow-up answer reflects earlier context.
