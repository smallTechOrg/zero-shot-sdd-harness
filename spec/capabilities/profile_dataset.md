# Capability: Profile Dataset

## What It Does
On upload, loads a tabular file locally and produces a structured profile (columns, types, ranges, null counts, distinct counts, sample rows) that becomes the schema context the agent reasons over.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | uploaded file (CSV; Excel in later phase) | multipart upload | yes |
| filename | string | upload metadata | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_id | string (uuid) | DB ([Dataset](../data.md#entity-dataset)) + response |
| profile | JSON (per-column: name, dtype, non_null, null_count, distinct_count, min, max, sample_values) | DB + response |
| sample_rows | JSON (first N=5 rows) | DB + response |
| row_count, column_count | int | DB + response |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | persist uploaded file under the datasets dir | fatal — return 400, no dataset row |
| pandas | read + profile the file locally | fatal — set error "could not parse file" |

WHEN profiling, the agent SHALL NOT send raw rows to the LLM; only the derived profile and at most N sample rows are ever eligible to leave the machine (see [privacy boundary](../architecture.md#privacy-boundary)).

## Business Rules
- The file is stored on disk; only its profile + sample rows are persisted as structured JSON.
- Files up to ~100MB are accepted. WHEN a file exceeds the limit, the upload SHALL be rejected with a clear message.
- Sample row count is capped (default 5) regardless of file size.
- Numeric/datetime ranges are computed; free-text columns report distinct count only (no value dump).

## Success Criteria
- [ ] Uploading a CSV returns a `dataset_id` and a profile listing every column with its inferred type.
- [ ] `row_count` matches the actual file row count (computed locally, not sampled).
- [ ] A non-tabular / corrupt file returns a 400 with a readable message and creates no dataset.
- [ ] No raw data row beyond the N-row sample appears in any LLM request payload (asserted in tests).
