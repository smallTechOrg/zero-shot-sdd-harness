# Capability: Persistent Session

## What It Does
Persists the uploaded dataset and the full query/answer history in SQLite so they survive a page reload — the UI rehydrates by re-fetching, with no client-only state and no server-side session object.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| (none — read on load) | — | UI calls `GET /datasets`, `GET /queries`, `GET /audit` | n/a |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset list (newest first) | JSON | UI active-dataset restore |
| query history (per dataset, newest first) | JSON | UI history list + answer re-display |
| audit list | JSON | UI audit panel |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | read `datasets`, `queries`, `audit_log` | `api_error` surfaced; UI shows load error, not a blank crash |

## Business Rules
- All durable state lives in `data/agent.db`; reload = re-fetch, never regenerate.
- On load the UI selects the most-recent dataset as active and loads its history.
- No authentication / no cookies — single local user, one implicit session.

## Success Criteria
- [ ] After uploading a dataset and asking a question, reloading `http://localhost:8001/app/` shows the same active dataset, the prior question + answer + table, and the audit history — all re-fetched from SQLite.
- [ ] `GET /datasets` and `GET /queries` return the persisted rows after a server restart (data is on disk, not in memory).
- [ ] With an empty database, load shows the upload empty-state without error.
