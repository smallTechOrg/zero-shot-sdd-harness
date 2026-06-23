# Data Model

## Storage Technology

**SQLite** (via SQLAlchemy 2.0 + Alembic) for all persistent metadata: sessions, datasets, messages, and query audit log. File path configured as `AGENT_DATABASE_URL=sqlite:///./data/analyst.db`.

**DuckDB** (in-process, in-memory per request) for analytical query execution. No persistent DuckDB file. DuckDB reads uploaded files directly from the filesystem.

**Filesystem** (`data/uploads/<session_id>/`) for raw dataset files (CSV, Excel, JSON).

The existing `RunRow` table (from the boilerplate skeleton) is retained but unused by the analyst agent. It stays in the schema to avoid breaking the initial migration.

---

## Entities

### Entity: `Session`

Represents one user's analytical workspace. A session owns datasets and messages and persists across browser sessions via `localStorage`.

**SQLite table:** `sessions`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key, server-generated |
| `name` | TEXT | yes | Display name, default "Session {n}" |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | UTC creation time |
| `updated_at` | TIMESTAMP WITH TIMEZONE | yes | UTC last modification time |

---

### Entity: `Dataset`

Represents one uploaded file within a session. Stores schema metadata (column names + types + row count) so the agent can build schema context without re-reading the file.

**SQLite table:** `datasets`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key, server-generated |
| `session_id` | TEXT (UUID FK → sessions.id) | yes | Owning session |
| `name` | TEXT | yes | Original filename (e.g. `sales.csv`) |
| `file_path` | TEXT | yes | Absolute filesystem path to the uploaded file |
| `file_type` | TEXT | yes | `csv` \| `xlsx` \| `json` |
| `row_count` | INTEGER | yes | Number of rows in the dataset (from DuckDB at upload time) |
| `columns_json` | TEXT (JSON) | yes | JSON array of `{"name": str, "type": str}` objects — column names and DuckDB-inferred types |
| `size_bytes` | INTEGER | no | File size in bytes |
| `uploaded_at` | TIMESTAMP WITH TIMEZONE | yes | UTC upload time |

**Index:** `(session_id)` for fast dataset lookup per session.

---

### Entity: `Message`

Represents one turn in the conversation. Both user questions and assistant responses are stored here. Assistant messages store the full `RichResponseModel` as JSON.

**SQLite table:** `messages`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key, server-generated |
| `session_id` | TEXT (UUID FK → sessions.id) | yes | Owning session |
| `role` | TEXT | yes | `user` \| `assistant` |
| `content` | TEXT | yes | User: plain text question. Assistant: JSON-serialized `RichResponseModel` |
| `status` | TEXT | yes | `pending` \| `completed` \| `failed` (assistant only; user messages are always `completed`) |
| `error` | TEXT | no | Error message if `status=failed` |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | UTC creation time |

**Index:** `(session_id, created_at)` for ordered conversation history fetch.

---

### Entity: `QueryLog`

Audit record for every SQL query the agent executes via DuckDB. Written by the `execute_query` node regardless of success or failure.

**SQLite table:** `query_logs`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key, server-generated |
| `session_id` | TEXT (UUID FK → sessions.id) | yes | Session that originated the query |
| `message_id` | TEXT (UUID FK → messages.id) | yes | Assistant message this query belongs to |
| `dataset_name` | TEXT | yes | Name of the primary dataset queried (first table in FROM clause, or all if multi-dataset) |
| `sql` | TEXT | yes | The exact SQL string executed |
| `row_count` | INTEGER | no | Number of rows returned (null on error) |
| `latency_ms` | INTEGER | no | Query execution time in milliseconds (null on error) |
| `error` | TEXT | no | DuckDB error message if execution failed |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | UTC timestamp of query execution |

**Index:** `(session_id, created_at)` for audit log listing.

---

### Entity: `RunRow` (retained from boilerplate skeleton)

The original boilerplate table. Retained to avoid conflicts with the existing Alembic migration `0001_initial.py`. Not used by the analyst agent.

**SQLite table:** `runs`

See `src/db/models.py` (existing definition unchanged).

---

## Pydantic Domain Models (not stored — used for type safety at API and graph boundaries)

### `ColumnSchema`
```python
class ColumnSchema(BaseModel):
    name: str
    type: str  # DuckDB type string, e.g. "VARCHAR", "DOUBLE", "DATE"
```

### `DatasetModel`
```python
class DatasetModel(BaseModel):
    dataset_id: str
    session_id: str
    name: str
    file_path: str
    file_type: str
    row_count: int
    columns: list[ColumnSchema]
    uploaded_at: datetime
```

### `MessageModel`
```python
class MessageModel(BaseModel):
    message_id: str
    session_id: str
    role: str  # "user" | "assistant"
    content: str
    status: str  # "pending" | "completed" | "failed"
    error: str | None = None
    created_at: datetime
```

### `QueryResultModel`
```python
class QueryResultModel(BaseModel):
    columns: list[str]
    rows: list[list[Any]]  # up to 500 rows
    row_count: int          # total rows from DuckDB (may exceed 500)
```

### `ChartSpec`
```python
class ChartSpec(BaseModel):
    type: str           # "bar" | "line" | "pie"
    labels: list[str]   # X-axis labels or pie slice labels
    datasets: list[dict]  # Chart.js dataset objects: {"label": str, "data": list[float]}
```

### `RichResponseModel`
```python
class RichResponseModel(BaseModel):
    narrative: str               # markdown text
    query_result: QueryResultModel | None = None
    chart_spec: ChartSpec | None = None
    sql: str | None = None       # the SQL that was executed (shown in UI on hover)
    query_log_id: str | None = None
```

### `SessionModel`
```python
class SessionModel(BaseModel):
    session_id: str
    name: str
    created_at: datetime
    dataset_count: int = 0
    message_count: int = 0
```

---

## DuckDB View Registration (runtime, not persisted)

When the `execute_query` node runs, it registers each dataset in the session as a named DuckDB view using the dataset's `name` (without extension) as the view name:

| Dataset file | DuckDB view name |
|-------------|-----------------|
| `sales.csv` | `sales` |
| `customers.xlsx` | `customers` |
| `orders.json` | `orders` |

The LLM is told the view names in the schema context so it references them correctly in SQL. If two datasets have the same base name, a `_2` suffix is appended.

---

## Relationships

```
Session 1 ──── N Dataset
Session 1 ──── N Message
Session 1 ──── N QueryLog
Message  1 ──── N QueryLog   (one assistant turn may generate multiple SQL queries in Phase 2+; Phase 1 = one query per turn)
```

---

## Data Lifecycle

| Entity | Created | Updated | Deleted |
|--------|---------|---------|---------|
| `Session` | On `POST /sessions` | On rename (Phase 2) | On `DELETE /sessions/{id}` (Phase 2) |
| `Dataset` | On `POST /datasets` | Never (immutable after upload) | Cascade on session delete (Phase 2); file removed from filesystem |
| `Message` | User message: on `GET /chat` request received. Assistant message: created as `pending` at start of graph, updated to `completed` or `failed` at `finalize`/`handle_error` | Status + content updated by `finalize`/`handle_error` | Cascade on session delete (Phase 2) |
| `QueryLog` | On `execute_query` node completion | Never (immutable audit record) | Cascade on session delete (Phase 2) |

---

## Sensitive Data

No PII or credentials are stored in the database. Uploaded dataset files may contain user data — they are stored locally on the user's machine (single-user tool) and never transmitted to external services except as SQL-derived results (not raw rows) interpreted by Gemini. No encryption or access control is in scope for Phase 1.

---

## Alembic Migration Plan

| Migration | File | Changes |
|-----------|------|---------|
| `0001_initial` | `alembic/versions/0001_initial.py` | Creates `runs` table (existing, unchanged) |
| `0002_analyst` | `alembic/versions/0002_analyst.py` | Creates `sessions`, `datasets`, `messages`, `query_logs` tables + indexes |
