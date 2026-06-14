# Capability: CSV Upload

**What it does:** Accept a CSV file from the user, save it to disk, parse its structure with pandas, and persist metadata (filename, row count, column names, timestamp) to SQLite — returning an `upload_id` the user can reference in later queries.

---

## Inputs

| Input | Source | Type | Constraints |
|-------|--------|------|-------------|
| `file` | HTTP multipart/form-data | Binary file | Must be a valid CSV; must have at least one header row and one data row; max file size not enforced in v0.1 |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| `id` | UUID string | Unique identifier for this upload; used by the query capability |
| `filename` | String | UUID-based on-disk filename (e.g. `3f2a...csv`) |
| `original_filename` | String | The name the user's browser reported |
| `row_count` | Integer | Number of data rows (excluding header) |
| `columns` | List[String] | Ordered column header names as detected by pandas |
| `uploaded_at` | ISO 8601 datetime (UTC) | Timestamp of successful storage |

## Processing Steps

1. Receive multipart request at `POST /api/uploads`
2. Validate that a file field is present and non-empty
3. Generate a UUID4; construct the on-disk path `uploads/<uuid>.csv`
4. Write the raw file bytes to disk
5. Read the saved file with `pandas.read_csv()`; catch `ParserError` and `EmptyDataError`
6. Extract `len(df)` (row count) and `list(df.columns)` (column names)
7. Insert a row into the `uploads` SQLite table
8. Return the upload record as JSON

## External Calls

| Call | Purpose |
|------|---------|
| Disk write (`open` + `write`) | Persist raw CSV to `uploads/` |
| `pandas.read_csv()` | Parse CSV to extract structure |
| SQLAlchemy `session.add()` + `session.commit()` | Insert upload record into SQLite |

No LLM call is made during upload.

## Error Cases

| Error | Trigger | HTTP Status | Response |
|-------|---------|-------------|----------|
| No file in request | Missing `file` field | 400 | `{"detail": "No file provided"}` |
| Not a valid CSV | pandas `ParserError` | 422 | `{"detail": "File could not be parsed as CSV: <error message>"}` |
| Empty CSV | pandas `EmptyDataError` or row_count == 0 | 422 | `{"detail": "CSV file contains no data rows"}` |
| Disk write failure | OS error on file write | 500 | `{"detail": "Failed to save file to disk"}` |
| Database error | SQLAlchemy exception | 500 | `{"detail": "Database error"}` |

## Success Criteria

- [ ] Uploading a valid 100-row CSV returns 200 with correct `row_count` (100) and `columns` list
- [ ] The file appears on disk under `uploads/<uuid>.csv`
- [ ] A corresponding row exists in the `uploads` SQLite table after upload
- [ ] Uploading a `.txt` file disguised as CSV that is not tabular returns 422
- [ ] Uploading an empty file (0 bytes) returns 422
- [ ] A second upload of a different file produces a different `id`
