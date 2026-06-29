# Capability: Multi-File Analysis

## What It Does

Users can upload multiple CSV (and Excel) files in a single session and ask questions that span multiple files — joining them on common columns, comparing them side-by-side, or analysing them independently.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| Additional CSV or Excel file(s) | multipart/form-data binary | POST /sessions/{session_id}/files | Yes (at least 2 total files in session) |
| Question referencing multiple files | string | POST /sessions/{session_id}/messages | Yes |
| session_id | UUID string | URL path parameter | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Profile card for each new file | object | API response + `files` table |
| Prose answer spanning multiple files | string | API response + `messages` table |
| Plotly chart (optional) | JSON dict or null | `chart_json` field in API response |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Write each uploaded file to session temp directory | Return HTTP 500; do not save DB record |
| SQLite (session DB) | INSERT file record per upload; SELECT all files for session on Q&A | Return HTTP 500 |
| LLM (Gemini) | Code generation with multi-file schema context | Return error message to user |
| Code execution sandbox | exec() with `dfs` containing all DataFrames | Catch exception; return error message |

## Business Rules

- When multiple files are uploaded to a session, the `dfs` dict in the exec() sandbox contains all DataFrames keyed by filename stem:
  ```python
  dfs = {
      "sales": pd.DataFrame(...),
      "customers": pd.DataFrame(...),
  }
  ```
- The LLM prompt includes schema + stats for ALL uploaded files, each clearly labelled by filename stem
- Excel files (`.xlsx`) are read with `pandas.read_excel()` (requires openpyxl); profile and Q&A work identically to CSV
- Uploading a file with the same stem as an existing file in the session overwrites the previous file and re-profiles it
- Maximum of 10 files per session; uploading an 11th returns HTTP 400
- Maximum file size per file: 50 MB

## Phase 1 UI Stub

- The upload dropzone accepts only `.csv` files and shows the label "CSV only — Excel support coming in Phase 2"
- A disabled button labelled "Upload another file [Coming in Phase 2]" is shown below the profile card
- The stub is clearly non-functional: the button is visually greyed out and does not respond to clicks

## Phase

Phase 2. Not implemented in Phase 1. Phase 1 shows clearly-labelled UI stubs only.

## Success Criteria

- [ ] Upload two CSV files to the same session → ask "join these on customer_id" → response reflects the merged DataFrame correctly
- [ ] Upload an Excel (.xlsx) file → profile card appears with correct column types and row count
- [ ] Upload 3 CSV files → ask a question referencing all three → agent answers correctly using all three DataFrames
- [ ] Attempt to upload an 11th file → server returns HTTP 400 with a clear message
- [ ] LLM prompt for a multi-file question includes schema context for all uploaded files, each labelled by filename stem
