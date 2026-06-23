# Capability: Dataset Management

## What It Does

Accepts uploaded CSV, Excel (.xlsx), and JSON files, stores them per user session, infers their schema via DuckDB, and makes them immediately queryable by the analyst agent.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `session_id` | string (UUID) | `POST /datasets` form field | Yes |
| `file` | multipart file upload | `POST /datasets` form field | Yes |
| File type | `.csv` \| `.xlsx` \| `.json` (inferred from extension) | File name | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Dataset record | `Dataset` SQLite row (id, name, file_path, row_count, columns_json) | SQLite `datasets` table |
| Saved file | Raw file bytes | `data/uploads/<session_id>/<filename>` on filesystem |
| `DatasetModel` | Pydantic model (id, name, row_count, columns) | `POST /datasets` JSON response (201) |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Filesystem | Write file to `data/uploads/<session_id>/` | Return 500; do not write SQLite record |
| DuckDB (in-memory) | Load file, infer schema, count rows | Return 400 with parse error message; remove partially written file |
| SQLite | INSERT Dataset row | Return 500; remove saved file (rollback) |

## Business Rules

- Accepted file types: `.csv`, `.xlsx`, `.json` only. Any other extension returns 400.
- Maximum file size: 100 MB. Larger files return 400.
- File is saved before DuckDB schema inference. If DuckDB fails to parse the file, the saved file is removed and 400 is returned.
- Excel files are loaded via `openpyxl` into a pandas DataFrame, then registered with DuckDB via `duckdb.register()`. The first sheet is used.
- Column names are taken exactly as DuckDB infers them from the file. No normalization.
- `row_count` is computed at upload time and stored; it is not re-computed on each query.
- Two datasets with the same base name in the same session are disambiguated with a `_2` suffix in the DuckDB view name (the SQLite `name` field stores the original filename).
- The `data/uploads/<session_id>/` directory is created if it does not exist at upload time.
- The session must exist (valid `session_id`) — 404 if not found.

## Success Criteria

- [ ] A 1 MB CSV file uploaded via `POST /datasets` returns 201 with correct `row_count`, `name`, and `columns` array within 5 seconds.
- [ ] An Excel (.xlsx) file with multiple columns is accepted; inferred column types and row_count are correct.
- [ ] A JSON file (array of objects) is accepted and schema is correctly inferred.
- [ ] A `.pdf` file returns 400 with a clear error message.
- [ ] A file larger than 100 MB returns 400.
- [ ] `GET /datasets?session_id=<id>` lists all datasets uploaded to that session.
- [ ] After server restart, dataset records remain in SQLite and files remain on disk.
- [ ] Two files with the same name uploaded to the same session are both stored (second gets `_2` DuckDB view name).
