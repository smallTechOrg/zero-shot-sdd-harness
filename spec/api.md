# API

---

## API Style

REST (FastAPI), JSON. Every response uses the envelope from `src/api/_common.py`: success → `{"data": ..., "error": null}` via `ok(data)`; failure → HTTP error with `{"detail": {"code", "message"}}` raised via `api_error(code, message, status)`. Served same-origin with the UI at `http://localhost:8001`. One router per resource: `datasets`, `queries`, `audit`.

> The skeleton's `/runs` router is repurposed/replaced by these. `/health` stays.

---

## Endpoints (Phase 1)

### `POST /datasets`

Upload one CSV → ingest into a `ds_<id>` table.

- **Request:** `multipart/form-data` with a `file` field (the CSV). Optional `name` field (defaults to filename).
- **Success (200):**
```json
{ "data": {
    "id": "3f2a…",
    "name": "sales.csv",
    "table_name": "ds_3f2a…",
    "row_count": 1240,
    "columns": [{"name": "region", "type": "TEXT"}, {"name": "revenue", "type": "REAL"}],
    "created_at": "2026-06-23T10:00:00Z"
}, "error": null }
```
- **Errors:** `BAD_CSV` (400) malformed/empty CSV or no header; `EMPTY_FILE` (400); `INGEST_FAILED` (500).
- **Side-effects:** creates `datasets` row, `ds_<id>` table, an `audit_log` (op `ingest`) entry.

### `GET /datasets`

List uploaded datasets (newest first) — used for session restore.

- **Success (200):** `{ "data": [ {dataset summary as above}, … ], "error": null }`

### `GET /datasets/{id}`

Fetch one dataset's metadata (schema/columns/row_count).

- **Success (200):** `{ "data": {dataset summary}, "error": null }`
- **Errors:** `NOT_FOUND` (404).

### `POST /queries`

Ask a natural-language question against a dataset. Runs the text-to-SQL graph synchronously.

- **Request (JSON):**
```json
{ "dataset_id": "3f2a…", "question": "What is total revenue by region?" }
```
- **Success (200):**
```json
{ "data": {
    "id": "9c11…",
    "dataset_id": "3f2a…",
    "question": "What is total revenue by region?",
    "generated_sql": "SELECT region, SUM(revenue) AS total FROM ds_3f2a… GROUP BY region",
    "answer_text": "Revenue is concentrated in the West region …",
    "result_columns": ["region", "total"],
    "result_rows": [["West", 540000], ["East", 312000]],
    "row_count": 2,
    "status": "completed",
    "error": null,
    "created_at": "2026-06-23T10:05:00Z"
}, "error": null }
```
- **Failure (still 200 with `status:"failed"`):** `generated_sql`/`answer_text` may be null and `error` is set (e.g. sandbox rejection, SQL error, LLM error). The audit entry records the failure.
- **Errors (HTTP):** `NOT_FOUND` (404) unknown `dataset_id`; `BAD_REQUEST` (400) empty question.
- **Side-effects:** creates `queries` row, writes an `audit_log` (op `query`) entry.

### `GET /queries?dataset_id=…`

List the query/answer history (newest first) — used for session restore. `dataset_id` optional; omit for all.

- **Success (200):** `{ "data": [ {query object as above}, … ], "error": null }`

### `GET /audit?limit=…`

List audit entries (newest first) — powers the audit panel. Optional `dataset_id`, `limit` (default 100).

- **Success (200):**
```json
{ "data": [ {
    "id": "…", "operation": "query", "dataset_id": "3f2a…", "query_id": "9c11…",
    "sql_text": "SELECT region, SUM(revenue) …",
    "row_count": 2, "columns": ["region", "total"],
    "duration_ms": 38, "success": true, "error_message": null,
    "created_at": "2026-06-23T10:05:00Z"
}, … ], "error": null }
```

### `GET /health`

Unchanged skeleton endpoint — liveness probe.

---

## Deferred endpoints (later phases, not built now)

- Phase 2: `PATCH /datasets/{id}` (rename), `DELETE /datasets/{id}`, multi-dataset query (`dataset_ids: [...]`).
- Phase 3: chart spec returned on `/queries` (`chart_spec` field).
- Phase 4: `POST /dashboards`, `POST /dashboards/{id}/items`, `GET /dashboards`.
