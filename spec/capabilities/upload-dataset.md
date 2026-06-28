# Capability: Upload & Profile a CSV

## What It Does
Accepts a CSV upload, stores it locally, and records a lightweight schema + small sample so the agent can later reason about it without ever sending the full data to the LLM.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | CSV (multipart) | user upload | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_id | string (uuid) | API response + Dataset row |
| schema | list[{name, dtype}] | Dataset.schema_json + response |
| sample | list[≤20 rows] | Dataset.sample_json + response |
| row_count | int | Dataset.row_count + response |
| stored file | file on disk | `src/data/datasets/<id>/<filename>` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | write the uploaded file | return `api_error("WRITE_FAILED", …, 500)` |
| pandas | read header + dtypes + sample rows | return `api_error("BAD_CSV", …, 400)` |

## Business Rules
- Only `.csv` accepted in Phase 1 (Excel deferred).
- The sample is capped at 20 rows; only schema + sample may later reach the LLM — never the full file.
- The full file is loaded for *execution* later, but profiling here reads only what is needed (header, dtypes, a head sample, row count).

## Success Criteria
- [ ] Uploading the sample olist CSV returns a `dataset_id`, a non-empty `schema`, a `sample` of ≤ 20 rows, and the correct `row_count`.
- [ ] A non-CSV / unparseable upload returns a 400 with a clear message (no crash).
- [ ] The Dataset row persists `schema_json` + `sample_json`; the file is on disk at the recorded path.
