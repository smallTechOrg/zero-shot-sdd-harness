# API

## API Style

REST + Server-Sent Events (SSE) for streaming answers. Single FastAPI process at `http://localhost:8001`, UI mounted at `/app/`. All JSON responses use the existing `ok(...)` / `api_error(...)` envelope.

## Endpoints / Commands

### `POST /datasets` — Phase 1

**Purpose:** Upload a CSV (Excel in Phase 3), store locally, auto-profile.

**Request:** `multipart/form-data` with a `file` field.

**Response:**
```json
{ "data": { "dataset_id": "uuid", "name": "sales.csv", "row_count": 12000,
  "profile": { "columns": [ { "name": "revenue", "dtype": "float64", "missing": 3,
    "min": 0.0, "max": 9999.0, "mean": 412.5, "distinct": 871 } ] } } }
```

**Errors:** 400 unsupported type / parse failure; 413 too large (>~100MB); 500 internal.

### `GET /datasets/{id}/profile` — Phase 1

**Purpose:** Fetch the stored profile for display.
**Response:** same `profile` shape as upload. **Errors:** 404 unknown dataset.

### `GET /datasets` — Phase 3

**Purpose:** List the library. **Response:** `{ "data": [ { "dataset_id", "name", "row_count", "created_at" } ] }`.

### `DELETE /datasets/{id}` — Phase 3
**Purpose:** Remove a dataset + bytes. **Errors:** 404.

### `POST /sessions/{session_id}/query` — Phase 1 (SSE)

**Purpose:** Ask a question; stream the analysis. `session_id` may be `new` to create one.

**Request:**
```json
{ "dataset_id": "uuid", "question": "What is total revenue by month?" }
```

**Response:** `text/event-stream`. Event types:
```
event: step    data: {"stage":"planning"}
event: step    data: {"stage":"running"}
event: code    data: {"code":"result = df.groupby(...)..."}
event: token   data: {"text":"Total revenue "}        # streamed answer chunks
event: result  data: {"kind":"scalar|table|chart","payload":{...}}   # Phase 2 for chart/table
event: done    data: {"run_id":"uuid","status":"completed",
                       "tokens":{"prompt":1200,"completion":340},"cost_usd":0.0012}
event: error   data: {"message":"..."}
```
In Phase 1 the `result`/`cost` fields may be minimal; `code`, `token`, `step`, `done` are real.

**Errors (pre-stream):** 400 missing dataset/question; 404 unknown dataset; 500.

### `GET /sessions/{id}/queries` — Phase 3 (audit trail)
**Purpose:** List a session's queries with code + result. **Response:** array of Query records.

### `GET /cost/daily` — Phase 2
**Purpose:** Running daily total. **Response:** `{ "data": { "date": "2026-06-28", "tokens": 23400, "cost_usd": 0.21 } }`.

## Authentication

None — single-user, localhost-only tool.
