# Capability: Profile Dataset

## What It Does
On upload of a CSV/Excel file, reads it locally and produces an auto-profile card — column names, inferred types, exact row count, sample rows, and data-quality flags — without sending any raw rows to the LLM.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | multipart file (`.csv`/`.xlsx`) | `POST /datasets` upload | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Dataset row | DB record (`datasets`) | SQLite |
| Stored file | file on disk | `data/datasets/<id>.<ext>` |
| Profile card | JSON `{columns, quality_flags, sample_rows, row_count, column_count}` | API response → UI Profile Card |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Store uploaded file | `api_error(500)` |
| pandas (+ openpyxl for xlsx) | Read file, infer dtypes, count rows, sample | `api_error(400)` on unparseable/unsupported/oversized |

## Business Rules
- No LLM call — profiling is pure local computation.
- Enforce the size limit (~100 MB); reject oversized files with a clear 400.
- Row count is the **exact** full count, not an estimate.
- Quality flags cover at least: null counts/percentages per column, and fully-empty or constant columns.
- `sample_rows` is a small fixed number of rows (e.g. 5), stored for use as LLM prompt context later.
- Name defaults to the filename stem.

## Success Criteria
- [ ] Uploading a well-formed CSV returns a profile with the correct column names, plausible inferred types, and the **exact** row count.
- [ ] An `.xlsx` file profiles correctly (openpyxl path).
- [ ] A column with nulls produces a quality flag naming the column and null proportion.
- [ ] An unsupported file (e.g. `.txt`) or oversized file returns a 400 with a helpful message, not a 500.
- [ ] The stored `datasets` row's `profile_json` round-trips to the same profile returned by the API.
