# Capability: CSV Upload and Profiling

## What It Does

When a user uploads a CSV file, the agent immediately profiles it without any LLM call and returns a structured summary card to the frontend. The profile is stored in the database for use in subsequent Q&A turns.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| CSV file | multipart/form-data binary | POST /sessions/{session_id}/files | Yes |
| session_id | UUID string | URL path parameter | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Profile card JSON | object | API response body + stored in `files` table |
| Quality flags list | array of flag objects | Embedded in profile card |

Profile card structure:
- `row_count`: total rows
- `column_count`: total columns
- `columns`: list of per-column profiles:
  - `name`: column name
  - `dtype`: pandas dtype as string (e.g. "float64", "object", "datetime64[ns]")
  - `null_count`: number of null values
  - `null_pct`: percentage of null values (0–100)
  - `sample_values`: first 3 non-null values, stringified
  - `stats` (numeric columns only): min, max, mean, std, p25, p50, p75
  - `value_counts` (object/categorical columns only): top-5 most frequent values with counts
- `quality_flags`: list of flagged issues:
  - `{type: "ERROR", column: null, message: "No data — file is empty"}`
  - `{type: "WARNING", column: "revenue", message: "42 null values (3.4%)"}`
  - `{type: "WARNING", column: null, message: "156 duplicate rows detected"}`
  - `{type: "INFO", column: "id", message: "Column has all-unique values — may be an ID column"}`
  - `{type: "ERROR", column: "revenue", message: "Column is entirely null"}`

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Write uploaded CSV to session temp directory | Return HTTP 500, do not save session record |
| SQLite (session DB) | INSERT into `files` table with profile JSON | Return HTTP 500 |

No LLM call is made during profiling.

## Business Rules

- Profile computation uses pandas only — zero LLM calls
- The profile JSON stored in the database and sent to the LLM in Q&A turns contains ONLY statistical metadata — never raw row values
- Files are saved to a per-session temp directory (e.g. `/tmp/sessions/{session_id}/`)
- Duplicate filenames within a session overwrite the previous file and re-profile
- Maximum file size: 50 MB (return HTTP 413 if exceeded)

## Quality Flags Logic

| Flag | Condition | Severity |
|------|-----------|----------|
| Empty file | row_count == 0 | ERROR |
| All-null column | null_count == row_count | ERROR |
| High-null column | null_pct > 20% | WARNING |
| Duplicate rows | df.duplicated().sum() > 0 | WARNING |
| Likely ID column | nunique == row_count AND dtype is object or int | INFO |

## Success Criteria

- [ ] Upload a 1000-row, 8-column CSV → profile card appears in the UI within 5 seconds
- [ ] Profile card shows correct row count, column types, and null percentages matching the actual file
- [ ] Quality flags appear for columns with > 20% nulls
- [ ] No raw row values appear in the profile JSON stored in DB or returned in the API response
- [ ] Uploading an empty CSV returns an ERROR quality flag and does not crash the server
- [ ] Uploading a file > 50 MB returns HTTP 413
