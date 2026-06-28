# Capability: Upload and Profile Dataset

## What It Does
Accepts a CSV upload (up to ~100MB), stores it locally, and auto-computes a profile —
columns, types, value ranges, missing-value counts, distinct counts — plus a bounded row sample.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | CSV (multipart) | user upload | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset record | row in `datasets` | DB ([data.md](../data.md)) |
| profile | JSON | `POST /api/datasets` response → UI profile panel |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| local filesystem | save uploaded file | return 400/500 with detail; no DB row |
| pandas | read + profile CSV | return 400 (parse) with a clear message |

## Business Rules
- Files up to ~100MB; reject larger or non-CSV with a clear error.
- Profile is computed over the FULL file; the bounded sample is for LLM context only.
- The stored file path is never exposed to the LLM.

## Success Criteria
- [ ] Uploading a 100k-row CSV returns a profile with correct row/column counts.
- [ ] Profile reports per-column dtype, missing_count, distinct_count, and range/top-values.
- [ ] A non-CSV or corrupt file returns a 400 with an actionable message, no DB row written.
