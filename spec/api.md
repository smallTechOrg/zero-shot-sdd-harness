# API

## API Style

REST + JSON over FastAPI (`api:app`). All responses use the skeleton envelope `{"data": ..., "error": null}` via `api._common.ok` / `api_error`. Same-origin; no auth (local-only single user).

## Endpoints / Commands

### `POST /datasets`

**Purpose:** Upload a CSV/Excel file, materialize it as a SQLite table, create (or reuse) a session, return the schema summary.

**Request:** `multipart/form-data` with field `file` (the CSV/.xlsx). Optional form field `session_id` (TEXT) to attach to an existing session; omitted → a new session is created.

**Response:**
```json
{ "data": {
  "session_id": "uuid",
  "dataset_id": "uuid",
  "table_name": "ds_uuid",
  "row_count": 1234,
  "columns": [{"name": "region", "type": "TEXT"}, {"name": "revenue", "type": "REAL"}]
}, "error": null }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Missing/empty file, unparseable CSV/Excel, zero columns |
| 500 | Ingestion or DB failure |

### `POST /sessions/{session_id}/ask`

**Purpose:** Ask a natural-language question against the session's dataset; run the analyst graph; persist a QaTurn.

**Request:**
```json
{ "question": "What is the total revenue by region?" }
```

**Response:**
```json
{ "data": {
  "turn_id": "uuid",
  "status": "completed",
  "answer_text": "Revenue is concentrated in...",
  "sql_text": "SELECT region, SUM(revenue) ... ",
  "result": { "columns": ["region", "total"], "rows": [["West", 9000], ["East", 7000]] },
  "error": null
}, "error": null }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Empty question |
| 404 | Unknown session_id / session has no dataset |
| 200 (status="failed") | SQL blocked by guard, SQL execution error, or LLM error — surfaced in `error` with status `failed`, turn persisted as failed |

### `GET /sessions/{session_id}`

**Purpose:** Read a session: its dataset summary and full Q&A history (for restart persistence).

**Response:**
```json
{ "data": {
  "session_id": "uuid",
  "title": "sales.csv",
  "dataset": { "dataset_id": "uuid", "table_name": "ds_uuid", "row_count": 1234, "columns": [...] },
  "turns": [ { "turn_id": "uuid", "question": "...", "answer_text": "...", "sql_text": "...", "result": {...}, "status": "completed", "created_at": "..." } ]
}, "error": null }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Unknown session_id |

### Existing (skeleton, unchanged): `GET /health`, `POST /runs`, `GET /runs/{id}`

Kept as-is; not part of the analyst surface.

## Internal Interface Contract (Phase 1)

> The crisp boundary between `backend-data` (Slice A, owner) and `backend-agent-api` (Slice B, consumer). Slice B codes against these signatures and never reimplements them. All live under `src/data/`.

```python
# src/data/ingest.py
def ingest_file(file_bytes: bytes, filename: str, session_id: str) -> dict:
    """Read CSV/Excel, create SQLite table ds_<dataset_id>, insert rows,
    write a datasets row + an audit_log(operation='ingest') row.
    Returns {dataset_id, table_name, row_count, columns: [{name,type}]}."""

# src/data/schema_summary.py
def schema_summary(table_name: str) -> list[dict]:
    """Return [{"name": str, "type": str}] for the data table (compact, no rows)."""

def sample_rows(table_name: str, n: int = 5) -> dict:
    """Return {"columns": [...], "rows": [[...], ...]} with at most n rows."""

# src/data/sql_guard.py
class SqlNotAllowed(Exception): ...

def assert_read_only(sql: str) -> str:
    """Return the SQL if it is a single read-only SELECT/WITH...SELECT statement.
    Raise SqlNotAllowed otherwise (any INSERT/UPDATE/DELETE/DROP/ALTER/ATTACH/
    PRAGMA-write/CREATE/REPLACE/multiple-statements/comments-hiding-DML)."""

# src/data/executor.py
def run_read_only(sql: str) -> dict:
    """Execute SQL on a READ-ONLY SQLite connection (mode=ro / query_only=ON).
    Return {"columns": [...], "rows": [[...], ...]}. Raises on SQL error."""

# src/data/audit.py
def log_operation(*, session_id: str | None, operation: str, question: str | None,
                  sql_text: str | None, rows_returned: int | None,
                  success: bool, error_message: str | None) -> None:
    """Persist one audit_log row."""
```

Slice B also owns session creation/lookup helpers in `src/api/sessions.py` (or `src/domain/analyst.py`); these are not part of Slice A's contract.

## Authentication

None. Local single-user, same-origin.
