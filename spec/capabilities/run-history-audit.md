# Capability: Run-History Audit

## What It Does
Persists every query as a durable, reproducible record (question, exact generated code, result,
chart spec, status, timestamp) and exposes it for retrieval.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string (UUID) | query string | for list |
| analysis id | string (UUID) | path | for single |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| run list | JSON array | `GET /api/analyses?dataset_id=...` |
| single run | JSON | `GET /api/analyses/{id}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite (SQLAlchemy) | read `analyses` rows | 500 with detail; never expose file paths |

## Business Rules
- Records are written for completed AND failed runs (audit holds either way).
- Records are immutable after terminal status.
- The exact code stored must be the code that produced the result (reproducibility).

## Success Criteria
- [ ] After a query, `GET /api/analyses/{id}` returns the question, code, result, chart_spec,
      and a UTC timestamp matching the run.
- [ ] A failed run still appears in history with `status=failed` and the last attempted code.
