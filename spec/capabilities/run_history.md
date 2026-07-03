# Capability: Run History

## What It Does
Saves every question as a full, revisitable record (question, code, result, charts, final answer, timestamps, dataset) and lets the user reopen a past run or re-run it against the current data.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id / session_id | str | `GET /runs?dataset_id=&session_id=` | no (filters) |
| run_id | str | `GET /runs/{id}`, `POST /runs/{id}/rerun` | yes for detail/re-run |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| History list | list[{run_id, question, status, created_at}] | API + UI History panel |
| Run detail | full run payload | API + UI |
| Re-run | a NEW run row | SQLite + API + UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Query/insert `runs` | `api_error` on not-found |
| Gemini + pandas subprocess (re-run only) | Re-execute the saved question via the agent | Same as analyze_dataset |

## Business Rules
- Every run (Phase 1 onward) is already persisted; this capability adds list/detail/re-run surfaces over that data.
- **Re-run creates a new run** against the current dataset — the original record is never mutated (so results can be compared over time as data changes).
- History is ordered newest-first and filterable by dataset (and session in Phase 2).
- Persistence survives restarts (SQLite on disk) — the workspace outlives a session.

## Success Criteria
- [ ] After asking several questions, `GET /runs?dataset_id=` returns them newest-first with question + status + timestamp.
- [ ] `GET /runs/{id}` returns the saved answer, chart, table, and exact code identical to when it was first produced.
- [ ] `POST /runs/{id}/rerun` produces a new run row (new id) and leaves the original unchanged.
- [ ] History persists across a server restart.
