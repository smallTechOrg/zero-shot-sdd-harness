# API

---

## API Style

REST (FastAPI), single origin `:8001`, serving the static UI at `/app/`. All JSON responses use the boilerplate envelope `ok(data)` → `{"data": ..., "error": null}` and `api_error(code, msg, status)` → `{"detail": {"code", "message"}}` from `src/api/_common.py`. The **live step stream** uses **Server-Sent Events (SSE)** — chosen over polling so the plan/steps/retries appear in real time with a simple, single long-lived `GET`, and over WebSockets because the stream is one-directional (server→browser) and short-lived.

> This contract is the seam between the backend and frontend slices — both build against it concurrently.

## Endpoints / Commands

### `POST /datasets`  *(Phase 1)*

**Purpose:** upload a CSV; store it locally, compute schema + ≤ 20 sample rows, create a Dataset.

**Request:** `multipart/form-data` with a single `file` field (the CSV).

**Response:**
```json
{ "data": { "dataset_id": "uuid", "filename": "olist_orders_dataset.csv",
            "row_count": 99441, "schema": [{"name": "order_status", "dtype": "object"}],
            "sample": [{"...": "≤20 rows"}] }, "error": null }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | No file / not a `.csv` / unparseable by pandas |
| 500 | Disk write or profiling failure |

### `POST /datasets/{dataset_id}/runs`  *(Phase 1)*

**Purpose:** ask a question — create a Run and dispatch the agent. Returns immediately with the `run_id`; progress is consumed via the SSE stream.

**Request:**
```json
{ "question": "How many orders are there for each order_status?" }
```

**Response:**
```json
{ "data": { "run_id": "uuid", "status": "running" }, "error": null }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | dataset_id not found |
| 400 | empty question |

### `GET /runs/{run_id}/stream`  *(Phase 1, SSE)*

**Purpose:** stream the live plan / steps / retries / final result as the graph runs.

**Response:** `text/event-stream`. Each event is `event: <type>\ndata: <json>\n\n`. Event types:
- `plan` — `{ "plan": "..." }`
- `step` — `{ "phase": "generate_code"|"execute_code", "attempt": 1, "message": "running code" }`
- `retry` — `{ "attempt": 2, "error": "KeyError: 'staus'" }`
- `final` — `{ "status": "completed", "answer": "...", "chart_spec": {...}, "table": [...], "code": "..." }`
- `error` — `{ "status": "failed", "error": "gave up after 3 attempts: ..." }`

The stream closes after `final` or `error`. (Implementation: the runner publishes node events to an in-process per-run queue that the SSE generator drains. Single-user, in-memory — no broker.)

### `GET /runs/{run_id}`  *(Phase 1)*

**Purpose:** fetch a completed/failed run (the persisted audit trail) — used to re-open a run and by tests.

**Response:**
```json
{ "data": { "run_id": "uuid", "dataset_id": "uuid", "question": "...",
            "plan": "...", "status": "completed", "answer": "...",
            "chart_spec": {...}, "table": [...],
            "steps": [{"attempt": 1, "code": "...", "ok": true, "error": null}],
            "tokens": 412 }, "error": null }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | run_id not found |

### Stubbed-for-later endpoints (defined now as shape, real later)

| Endpoint | Phase | Purpose |
|----------|-------|---------|
| `GET /datasets` | 3 | List the dataset library. |
| `POST /sessions`, `GET /sessions/{id}` | 3 | Create/resume a session with chat history. |
| `POST /sessions/{id}/runs` | 4 | Multi-dataset run over selected datasets. |
| `GET /history?dataset_id=` | 5 | Full run history grouped by dataset. |
| `GET /runs/{id}/download?fmt=csv` | 5 | Download a run's result. |

In Phase 1 the UI's stub panels do **not** call these — they render static "Coming soon" placeholders so a stub is never mistaken for a failing request.

## Authentication

None — single local user, localhost only, no auth/sessions in the security sense.
