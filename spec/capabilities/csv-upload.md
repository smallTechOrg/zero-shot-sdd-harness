# Capability: CSV Upload

## What It Does

Accepts a CSV file from the user, loads it into a named SQLite table, and returns the session ID plus the inferred column schema.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `file` | multipart/form-data binary | Browser file picker | Yes |
| filename | derived from `file.filename` | HTTP upload metadata | Yes (used to derive table name) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `session_id` | UUID string | JSON response body → browser |
| `table_name` | string (`{slug}_{session_id[:8]}`) | JSON response body → browser; stored in `upload_sessions` |
| `schema` | `list[{column: str, type: str}]` | JSON response body → browser |
| `row_count` | integer | JSON response body → browser |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite (`data/agent.db`) | `CREATE TABLE` + bulk `INSERT` | HTTP 422 with structured error; no partial table left behind (transaction rolled back) |

## Business Rules

- Table name is derived as `{slug}_{session_id[:8]}` where `slug` is the filename stem lowercased with non-alphanumeric characters replaced by `_`, truncated to 40 characters. Example: `"Sales Data Q1.csv"` → `sales_data_q1_a3f7b2c1`.
- Column type inference: for each column, attempt to cast all non-empty values to `int`; if all succeed, use `INTEGER`. Else attempt `float`; if all succeed, use `REAL`. Otherwise use `TEXT`. Empty cells are stored as NULL.
- Maximum CSV file size: 50 MB (enforced by FastAPI request body limit). Files over 50 MB return HTTP 413.
- Maximum columns: 200. Files with more columns return HTTP 422.
- The CSV must have a header row. Files without a header row are rejected with HTTP 422.
- Each upload creates a new `UploadSession` record regardless of filename — two uploads of the same file get different `session_id` values and different table names.
- Duplicate column names in the CSV are disambiguated by appending `_2`, `_3`, etc.

## Success Criteria

- [ ] A valid CSV upload returns HTTP 200 with `session_id`, `table_name`, `schema`, and `row_count` within 3 seconds for files up to 10 MB.
- [ ] The SQLite dynamic table exists and contains exactly the uploaded row count after the request completes.
- [ ] An upload with a non-CSV file (e.g. `.xlsx`) returns HTTP 422 with a human-readable error message.
- [ ] An upload with no header row returns HTTP 422.
- [ ] Two uploads of the same filename produce two different `session_id` and `table_name` values.
- [ ] A CSV with mixed numeric/text in a column correctly infers `TEXT` type for that column.
