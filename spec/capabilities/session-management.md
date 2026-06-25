# Capability: Session Management UI (C9)

## What It Does
Lets the user create, resume, rename, bulk-select, and delete conversation sessions.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| sessions list | JSON | `GET /sessions` | yes |
| session detail | JSON | `GET /sessions/{id}` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| sidebar list + actions | UI | Analyse sidebar |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| `GET /sessions`, `GET /sessions/{id}` | list / detail | 404 detail |
| `PATCH /sessions/{id}/name`, `DELETE /sessions/{id}`, `DELETE /sessions` | rename / delete | 404 |

## Business Rules
- Sessions sorted most-recently-updated first; each shows `turn_count` + `first_question` + relative time.
- +New, inline rename, bulk-select + Delete selected, Clear all (modal-confirmed).

## Success Criteria
- [ ] Creating a session, asking a question, and reopening it restores the turns.
- [ ] Renaming persists; deleting removes it and its runs (per cascade rules).
