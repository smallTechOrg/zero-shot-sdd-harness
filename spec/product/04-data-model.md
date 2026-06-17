# Data Model

## Storage Technology

SQLite via SQLAlchemy 2.0 (sync). Single file database, no server process required. Alembic manages schema migrations.

## Entities

### Entity: DataSource

Represents a connected data source. For v0.1 the only supported type is `csv`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID) | yes | Primary key |
| name | TEXT | yes | User-facing name (defaults to filename for CSV) |
| type | TEXT | yes | Enum: `csv` (future: `api`, `graphql`, `shell`) |
| description | TEXT | no | Optional user-provided description |
| file_path | TEXT | no | Absolute path on disk (CSV sources only) |
| row_count | INTEGER | no | Number of data rows (set after parse, CSV only) |
| column_names_json | TEXT | no | JSON-encoded list of column names (CSV only) |
| created_at | TIMESTAMP | yes | When the data source was connected |

---

### Entity: Tool

An executable tool registered against a DataSource. Each DataSource has one Tool in v0.1; the model supports multiple tools per source in the future.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID) | yes | Primary key |
| data_source_id | TEXT (FK → DataSource.id) | yes | Owning data source |
| name | TEXT | yes | Short name, e.g. `csv_query` |
| type | TEXT | yes | Executor type. Determines which executor branch handles dispatch. Enum: `csv_query` (future: `api_call`, `graphql_query`, `shell_exec`) |
| description | TEXT | yes | Shown to the LLM as the tool description |
| config_json | TEXT | no | Type-specific config (e.g. `{"table_name": "data"}` for csv_query) |
| created_at | TIMESTAMP | yes | When the tool was registered |

---

### Entity: ToolCapability

A single callable action that a Tool exposes. The LLM selects a capability by name and provides parameters matching the schema.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID) | yes | Primary key |
| tool_id | TEXT (FK → Tool.id) | yes | Owning tool |
| name | TEXT | yes | Capability name, e.g. `run_query`. Must be unique within a tool. |
| description | TEXT | yes | Shown to the LLM to explain what this capability does |
| parameter_schema_json | TEXT | yes | JSON Schema object describing the parameters. Example: `{"query": {"type": "string", "description": "A SQL SELECT statement"}}` |

---

### Entity: Session

A named conversation session on a DataSource. A user can have many sessions per DataSource.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID) | yes | Primary key |
| data_source_id | TEXT (FK → DataSource.id) | yes | The data source being queried |
| name | TEXT | no | Optional user-given name; defaults to "Session YYYY-MM-DD HH:MM" |
| created_at | TIMESTAMP | yes | Session start time |
| updated_at | TIMESTAMP | yes | Last activity time |

---

### Entity: QueryRecord

One natural language question submitted by the user within a Session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID) | yes | Primary key |
| session_id | TEXT (FK → Session.id) | yes | Owning session |
| question | TEXT | yes | The user's natural language question |
| answer | TEXT | no | The LLM's final plain-text answer (null while processing) |
| status | TEXT | yes | `pending` / `completed` / `failed` |
| error_message | TEXT | no | Error detail if status=failed |
| iteration_count | INTEGER | no | Number of tool calls made to reach the answer |
| query_history_json | TEXT | no | JSON array of `{"sql": str, "result": str, "is_error": bool}` entries — the full tool-call trace |
| input_tokens | INTEGER | no | Total input tokens across all LLM calls |
| output_tokens | INTEGER | no | Total output tokens across all LLM calls |
| total_tokens | INTEGER | no | Sum of input + output tokens |
| estimated_cost_usd | REAL | no | Estimated API cost in USD |
| api_request_count | INTEGER | no | Number of LLM API calls made |
| created_at | TIMESTAMP | yes | When the query was submitted |
| updated_at | TIMESTAMP | yes | When the record was last modified |

---

### Entity: AgentRun

Internal record tracking each LangGraph pipeline invocation. One per QueryRecord (one-to-one in practice).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID) | yes | Primary key |
| query_record_id | TEXT (FK → QueryRecord.id) | yes | The query this run serves |
| status | TEXT | yes | `pending` / `completed` / `failed` |
| error_message | TEXT | no | Error detail if failed |
| created_at | TIMESTAMP | yes | Run start time |
| updated_at | TIMESTAMP | yes | Last update |

---

## Relationships

```
DataSource (1) ──< Tool (N)
Tool (1) ──< ToolCapability (N)

DataSource (1) ──< Session (N)
Session (1) ──< QueryRecord (N)
QueryRecord (1) ──< AgentRun (N)
```

## Bootstrap: CSV Upload

When a CSV file is uploaded, the following records are created atomically:

1. `DataSource` — type=`csv`, file_path=..., row_count and column_names_json set after parse
2. `Tool` — type=`csv_query`, name=`csv_query`, config_json=`{"table_name": "data"}`
3. `ToolCapability` — name=`run_query`, description="Execute a SQL SELECT query against the dataset", parameter_schema_json=`{"query": {"type": "string", "description": "A valid SQL SELECT statement. The table is always named 'data'."}}`

## Data Lifecycle

- **DataSource**: created on upload; deleted via explicit user action (cascades to Tool, ToolCapability, Session, QueryRecord, AgentRun, and the CSV file on disk).
- **Tool / ToolCapability**: created with DataSource; deleted with DataSource.
- **Session**: created when user starts a new session; deleted with DataSource.
- **QueryRecord**: created when user submits a question; answer written after pipeline completes; deleted with Session.
- **AgentRun**: created at pipeline start; updated to `completed` or `failed` at end; deleted with QueryRecord.

## Sensitive Data

- CSV files may contain PII depending on what the user uploads. No special handling in v0.1 — files stored as-is on local disk. Multi-user deployments must add access controls before exposing this app.
- No API keys stored in the database.
