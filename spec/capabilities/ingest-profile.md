# Capability: Ingest & Auto-Profile a Dataset

## What It Does
Stores an uploaded CSV locally and computes a privacy-safe column profile (types, ranges, missing values) without ever exporting raw rows.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | multipart upload | `POST /datasets` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Dataset record | row | `datasets` table |
| DatasetProfile | json | `dataset_profiles` table + API response |
| stored bytes | file | `data/uploads/` (local only) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| local disk | write file bytes | 500, no record created |
| pandas | read + profile | 400 parse error |

## Business Rules
- Accept CSV up to ~100MB; reject larger (413) and unsupported types (400).
- Profile contains only aggregates: dtype, missing count, min/max/mean (numeric), distinct count, top categories. **No raw cell values.**
- Profiling must not hold multiple full copies of a 100MB file in memory unnecessarily.

## Success Criteria
- [ ] Uploading a CSV returns a `dataset_id` and a profile with one entry per column.
- [ ] `GET /datasets/{id}/profile` returns the same profile after restart (persisted).
- [ ] The profile JSON contains no raw row/cell values (asserted in test).
