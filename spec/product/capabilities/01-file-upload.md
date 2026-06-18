# Capability 01 — File Upload

## What It Does

Accepts a CSV or JSON file from the browser, validates its format and size, parses it into an in-memory pandas DataFrame, stores the raw file on disk, writes session metadata to SQLite, and caches the DataFrame for subsequent agent queries.

## Inputs

| Input | Source | Constraints |
|-------|--------|-------------|
| File (binary) | `multipart/form-data` field `file` in `POST /api/sessions` | Max 50 MB; extension must be `.csv` or `.json` |

## Outputs

| Output | Destination | Description |
|--------|-------------|-------------|
| Session record | SQLite `sessions` table | `session_id`, filename, file path, row count, column names, column dtypes, status, timestamps |
| DataFrame | In-memory process cache (`dict[session_id → DataFrame]`) | Parsed pandas DataFrame, keyed by `session_id` |
| Raw file | Local filesystem at `/tmp/datachat/<session_id>/<filename>` | Stored for potential future re-reads |
| API response | HTTP `201 Created` to client | `session_id`, `filename`, `row_count`, `column_names`, `column_dtypes`, `created_at` |

## Validation Rules (in order)

1. **File present:** Request must include the `file` field.
2. **Extension check:** Filename must end in `.csv` or `.json` (case-insensitive). Reject with 415.
3. **Size check:** File size must be ≤ 50 MB (52,428,800 bytes). Reject with 413.
4. **Parse check:** pandas must be able to read the file (`pd.read_csv` or `pd.read_json`). If parsing raises an exception, reject with 422 and include the exception message.
5. **Non-empty check:** The resulting DataFrame must have at least 1 row and 1 column. Reject with 422 with message "File appears to be empty."

> **Assumed:** No schema validation beyond non-empty. The agent will infer meaning from column names at query time.

## External Calls

| System | Call | Failure Handling |
|--------|------|-----------------|
| Local filesystem | Write file to `/tmp/datachat/<session_id>/` | Return 500; log the OS error |
| pandas | `pd.read_csv()` or `pd.read_json()` | Catch `Exception`; return 422 with parse error message |
| SQLite | `INSERT INTO sessions ...` | Return 500; log the DB error |

No calls to external APIs (no Gemini involved in upload).

## Error Cases

| Condition | HTTP Status | Client-Facing Message |
|-----------|-------------|----------------------|
| No file in request | 400 | "No file was provided." |
| Unsupported file extension | 415 | "Only CSV and JSON files are supported." |
| File exceeds 50 MB | 413 | "File exceeds the 50 MB size limit." |
| pandas cannot parse the file | 422 | "Could not parse the file: `{exception message}`" |
| DataFrame is empty | 422 | "File appears to be empty (no rows or no columns)." |
| Disk write failure | 500 | "Failed to save the uploaded file. Please try again." |
| SQLite insert failure | 500 | "Failed to create session. Please try again." |

## Success Criteria

- [ ] Uploading a valid 10 MB CSV returns `201` with correct `row_count` and `column_names`.
- [ ] Uploading a valid JSON file (array of objects) returns `201` with correct schema.
- [ ] Uploading a file larger than 50 MB returns `413`.
- [ ] Uploading a `.xlsx` file returns `415`.
- [ ] Uploading a malformed CSV (unpaired quotes, wrong delimiter) returns `422` with an error message.
- [ ] After a successful upload, the DataFrame is retrievable from the in-memory cache by `session_id`.
- [ ] After a successful upload, a `Session` row exists in SQLite with `status = "ready"`.

## Dependencies

- None (this capability has no dependency on other capabilities; it is the entry point of every session).
