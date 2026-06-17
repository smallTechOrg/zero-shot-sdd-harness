# Capability 1: Connect a CSV File as a Data Source

## Overview

The user uploads a CSV file. The system creates a `DataSource` record, a `Tool` of type `csv_query`, and a `ToolCapability` named `run_query`. The data source then appears on the home page and is available for sessions.

## User-Facing Behaviour

1. User selects a CSV file on the home page and clicks "Connect".
2. The system validates the file, saves it to disk, and parses it to extract column names and row count.
3. The system creates the DataSource + Tool + ToolCapability records atomically.
4. The user is redirected to the DataSource detail page (sessions list).

## Inputs

- `file`: a `multipart/form-data` CSV file upload

## Outputs

- New `DataSource` record in SQLite
- New `Tool` record: `{type: "csv_query", name: "csv_query", config: {table_name: "data"}}`
- New `ToolCapability` record: `{name: "run_query", parameter_schema: {"query": {"type": "string"}}}`
- Redirect to `GET /datasources/{id}`

## What Gets Stored

| Record | Key Fields Set |
|--------|---------------|
| DataSource | name (filename), type=csv, file_path, row_count, column_names_json |
| Tool | data_source_id, type=csv_query, name=csv_query, description, config_json |
| ToolCapability | tool_id, name=run_query, description, parameter_schema_json |

## Error Cases

| Error | Behaviour |
|-------|-----------|
| No file selected | JS validation message; form does not submit |
| File is not CSV | 400 response; user sees error message |
| File too large (>100MB) | 400 response; user sees size error |
| Disk write fails | 500 response; renders error.html |
| DB insert fails | 500 response; file cleaned up from disk; renders error.html |

## Success Criteria

- After upload, DataSource appears on home page with correct row count and column names
- Tool record exists with type=csv_query
- ToolCapability record exists with name=run_query and correct parameter_schema_json
- All three records share the correct FK chain (DataSource → Tool → ToolCapability)
- Redirects to DataSource detail page on success
