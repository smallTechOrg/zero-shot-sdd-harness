# Capability: Upload & Multi-format Ingest (C1, C11)

## What It Does
Accepts an uploaded data file (CSV/TSV/TXT/JSON/Excel), parses it with pandas, hashes it, saves it as CSV + Parquet, and registers it as a dataset.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | multipart upload | browser | yes |
| context | string (≤4000) | form field | no |
| notes_file | upload (.txt/.md) | form field | no |
| force | bool | query | no (default false) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset record | `datasets` row | SQLite |
| CSV + Parquet | files | `uploads/{id}.csv` / `.parquet` |
| response | JSON | `{dataset_id, filename, format, row_count, col_count, columns, context, auto_notes_status}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| pandas | parse file by extension | 400 unparseable/empty |
| disk | write CSV + Parquet | 500 write fail |
| LLM (async) | trigger C30 notes | non-fatal; `auto_notes_status=failed` |

## Business Rules
- Accept `.csv/.tsv/.txt/.json/.xlsx/.xls`; bad extension → 400.
- Compute sha256 of bytes; duplicate-check (see [duplicate-detection.md](duplicate-detection.md)) → 409 unless `force=true`.
- `format` recorded as csv|tsv|txt|json|excel; `origin=uploaded`.
- Pre-convert to Parquet on upload for fast loads (C27).

## Success Criteria
- [ ] Uploading a valid CSV returns 200 with correct `row_count`/`col_count` and writes both `.csv` and `.parquet`.
- [ ] Uploading each supported format (tsv/txt/json/xlsx/xls) parses correctly.
- [ ] A `.exe` (bad extension) returns 400; an empty file returns 400.
- [ ] A second identical upload returns 409 `duplicate_dataset`; with `force=true` it succeeds.
