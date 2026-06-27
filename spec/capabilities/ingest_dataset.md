# Capability: Ingest Dataset

## What It Does
Accepts an uploaded data file, stores it locally, parses it into a dataframe, and builds a bounded schema + sample/profile that can later be sent to the LLM.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | uploaded file (multipart) | user via `POST /datasets` | yes |
| file_format | derived (`csv`; `xlsx` from Phase 2) | file extension | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset record | `datasets` row (id, filename, format, local_path, row/column counts, schema_summary, status) | local SQLite |
| stored file | bytes on disk | `data/uploads/<id>.<ext>` |
| dataset response | JSON `data` (dataset_id, filename, format, counts, columns, status) | API caller |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (none) | parsing is fully local; no network call in this capability | record `status=failed` + `error_message`, return `PARSE_FAILED` |

## Business Rules
- The raw file is written only to the local filesystem; it is never transmitted to any external service.
- `schema_summary` (the only data that may later leave the machine) is bounded: column names + dtypes + a small sample of rows + per-column summary stats — never the full dataset.
- Phase 1 accepts only `.csv`. Non-CSV → `UNSUPPORTED_FORMAT`. (Phase 2 adds `.xlsx` via openpyxl, first sheet.)
- Reasonable sizes only in Phase 1 (up to a few thousand rows); a configurable cap rejects oversized files with `FILE_TOO_LARGE`. (Phase 3 raises the cap with bounded sampling + memory guards.)
- Each new operation (save, parse, profile) emits a structured log line.

## Success Criteria
- [ ] Uploading a valid CSV creates a `datasets` row with `status=ready`, correct `row_count`/`column_count`, and a non-empty `schema_summary` containing the real column names.
- [ ] The raw file exists at `data/uploads/<id>.csv` and no network call is made during ingest.
- [ ] Uploading a non-CSV in Phase 1 returns `UNSUPPORTED_FORMAT` (400) and creates no `ready` dataset.
- [ ] An unparseable file returns `PARSE_FAILED` (422) and records `status=failed`.
