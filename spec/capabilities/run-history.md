# Capability: Run History (Phase 2 — stub in Phase 1)

## What It Does
Persists and lets the user revisit every question (text · code · result · cost · timestamp) for a dataset.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | path | yes |
| question_id | string | path (detail) | for detail |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| questions list | [{id, question, cost_usd, created_at, status}] | `GET /datasets/{id}/questions` |
| question detail | {question, code, result, chart_spec, usage, created_at} | `GET /questions/{id}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | read `questions` for the dataset | 404 if dataset/question absent |

## Business Rules
- Phase 1 already **persists** every question; this capability adds the read/list/revisit surface and wires the UI History panel (a labelled stub in Phase 1).
- History is per dataset, newest first, paginated.

## Success Criteria
- [ ] Listing returns all questions for a dataset, newest first, each with cost + timestamp.
- [ ] Opening a past question shows its exact code and result.
- [ ] **State-survival:** after a page reload, the history list is still present and openable (guards detached-row bugs).
