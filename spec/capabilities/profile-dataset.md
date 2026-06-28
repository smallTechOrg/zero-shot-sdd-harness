# Capability: Profile Dataset

## What It Does
On upload, auto-profiles a CSV/Excel file (rows, columns, types, missing %, ranges, quality flags) and suggests 2–3 follow-up questions — without sending any raw row to the LLM.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | multipart upload (`.csv`/`.xlsx`) | `POST /datasets` | yes |
| filename | string | upload | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset_id | string | response + `datasets` row |
| profile | DatasetProfile JSON (rows, cols, per-column {name,dtype,missing_pct,min,max,distinct_count,safe_to_sample_labels,example_labels}) | response + `datasets.profile_json` |
| quality_flags | list of {column, issue} | inside profile |
| suggested_questions | list[str] (2–3) | response + `datasets.suggested_questions_json` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas/pyarrow | read full file → Parquet, compute stats | return 422 with a clear "couldn't parse file" message; nothing persisted |
| Gemini (gemini-2.5-flash) | suggest 2–3 questions from the **profile only** | degrade: persist profile, return an empty `suggested_questions` list (profiling still succeeds) |

## Business Rules
- Profiling reads the **full** DataFrame; statistics are computed over all rows, never a sample.
- Only the profile (schema + metadata) is ever sent to Gemini for suggestions — never rows. Example category labels are included only for columns with `distinct_count <= 50` (`MAX_CATEGORY_LABELS = 10`); high-cardinality columns expose count/missing only. See [architecture.md](../architecture.md#privacy-boundary).
- Upload normalised to `data/datasets/<id>.parquet`; the raw upload kept at `data/uploads/<id>.<ext>`.
- Quality flags: missing >30%, constant column, duplicate rows, mixed-type column.
- Files up to ~100MB accepted.

## Success Criteria
- [ ] Uploading a 50,000-row CSV returns a profile with correct row count, per-column dtype, and missing % computed over all rows.
- [ ] A high-cardinality column (e.g. an email/UUID column) has no `example_labels` in the profile; a low-cardinality column (e.g. region) has its labels.
- [ ] 2–3 suggested questions are returned and reference real column names.
- [ ] A malformed file returns 422 with a human message and persists nothing.
- [ ] Quality flags fire on a fixture with a >30%-missing column and a constant column.
