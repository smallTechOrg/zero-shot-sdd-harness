# Capability: Persist Session

## What It Does
Groups an uploaded dataset with its Q&A history into a session that survives server restarts and can be re-read.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | string | path | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| session view | `{session_id, title, dataset, turns[]}` | `GET /sessions/{id}` response |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | read sessions/datasets/qa_turns | 404 if session unknown |

## Business Rules
- Phase 1: exactly one dataset per session.
- The full Q&A history is returned ordered by `created_at`.
- Session state lives in SQLite, so it is unaffected by restart.

## Success Criteria
- [ ] `GET /sessions/{id}` returns the dataset summary and all prior turns.
- [ ] After a server restart, the same session id still returns its prior turns.
- [ ] An unknown session id returns 404.
