# API

## API Style

REST. JSON request/response bodies (except the upload endpoint which is `multipart/form-data`). All responses are wrapped in `{"ok": true|false, "data": {...}}` using the existing `api/_common.ok()` helper. Errors use `{"ok": false, "error": {"code": "...", "message": "..."}}`.

Base URL (development): `http://localhost:8001`

---

## Endpoints

### `GET /health`

**Purpose:** Liveness probe. Returns `{"ok": true}` if the FastAPI process is running. Does not check database connectivity.

**Request:** None

**Response:**
```json
{
  "ok": true
}
```

**Error cases:**

| Status | Condition |
|--------|-----------|
| — | No error cases; always returns 200 while the process is alive |

---

### `POST /upload`

**Purpose:** Accept a CSV file upload, parse it, create a named SQLite table, and return the session context.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | binary | Yes | The CSV file. Filename used to derive the table name slug. |

**Response (200 OK):**
```json
{
  "ok": true,
  "data": {
    "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "table_name": "sales_data_3fa85f64",
    "row_count": 1500,
    "schema": [
      {"column": "product_name", "type": "TEXT"},
      {"column": "quantity",     "type": "INTEGER"},
      {"column": "revenue",      "type": "REAL"}
    ]
  }
}
```

**Error cases:**

| Status | Code | Condition |
|--------|------|-----------|
| 413 | `FILE_TOO_LARGE` | File exceeds 50 MB |
| 422 | `INVALID_CSV` | File has no header row, cannot be parsed as CSV, or contains > 200 columns |
| 422 | `UNSUPPORTED_FORMAT` | File extension is not `.csv` |
| 500 | `DB_ERROR` | SQLite table creation or insert failed |

---

### `POST /query`

**Purpose:** Run the five-node LangGraph pipeline against an uploaded session and return the SQL, chart spec, and insight.

**Request:**
```json
{
  "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "question": "What are the top 5 products by total revenue?"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `session_id` | UUID string | Yes | Must match an existing `UploadSession` record |
| `question` | string | Yes | 1–2000 characters |

**Response (200 OK — successful pipeline run):**
```json
{
  "ok": true,
  "data": {
    "query_run_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "status": "completed",
    "sql": "SELECT product_name, SUM(revenue) AS total_revenue FROM sales_data_3fa85f64 GROUP BY product_name ORDER BY total_revenue DESC LIMIT 5",
    "chart_spec": {
      "type": "bar",
      "title": "What are the top 5 products by total reve...",
      "xKey": "product_name",
      "yKey": "total_revenue",
      "data": [
        {"product_name": "Widget A", "total_revenue": 45200.5},
        {"product_name": "Widget B", "total_revenue": 38100.0}
      ]
    },
    "insight": "Widget A leads with $45,200 in total revenue, 19% ahead of Widget B at $38,100. The top 5 products together account for 73% of all revenue in the dataset."
  }
}
```

**Response (200 OK — pipeline failed):**
```json
{
  "ok": true,
  "data": {
    "query_run_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "status": "failed",
    "sql": null,
    "chart_spec": null,
    "insight": null,
    "error": "SQL safety violation: only SELECT queries are permitted."
  }
}
```

> Note: Pipeline failures (safety violations, Gemini errors, SQL execution errors) return HTTP 200 with `status: "failed"` and an `error` field — not a 5xx. HTTP errors (bad request, not found) use standard 4xx codes.

**Error cases (HTTP-level):**

| Status | Code | Condition |
|--------|------|-----------|
| 404 | `SESSION_NOT_FOUND` | `session_id` not found in `upload_sessions` |
| 422 | `VALIDATION_ERROR` | `question` is empty or exceeds 2000 characters |
| 422 | `VALIDATION_ERROR` | `session_id` is not a valid UUID |

---

## Authentication

None in Phase 1. All endpoints are open. Authentication (session tokens / OAuth) is explicitly out of scope for Phase 1 and labelled as a stub in the UI.

---

## Shared Response Envelope

All successful responses:
```json
{"ok": true, "data": {...}}
```

All error responses:
```json
{"ok": false, "error": {"code": "SNAKE_CASE_CODE", "message": "Human-readable message."}}
```

The `api/_common.py` helpers `ok(data)` and `api_error(code, message, status)` implement this envelope.
