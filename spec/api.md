# API

> REST over FastAPI, single origin `http://localhost:8001`. Frontend served at `/app/`. All responses use the skeleton envelope: success → `{"data": <payload>, "error": null}` via `ok(data)`; failure → HTTP error with `{"detail": {"code": ..., "message": ...}}` via `api_error(code, message, status)`.

---

## API Style

REST. Phase-1 endpoints below. Later phases add list/history/compare/notes/cost endpoints (see `roadmap.md`).

## Endpoints / Commands

### `POST /datasets`

**Purpose:** Upload a CSV; ingest into local DuckDB and profile it. No LLM call.

**Request:** `multipart/form-data` with a `file` field (a `.csv`). (Excel rejected in Phase 1 with a clear message — stub.)

**Response (200):**
```json
{
  "data": {
    "id": "uuid",
    "name": "sales.csv",
    "row_count": 124000,
    "columns": [{"name": "region", "type": "VARCHAR"}, {"name": "sales", "type": "DOUBLE"}],
    "profile": {
      "row_count": 124000,
      "columns": [
        {"name": "region", "type": "VARCHAR", "nulls": 0, "distinct": 5},
        {"name": "sales", "type": "DOUBLE", "nulls": 12, "min": 0.0, "max": 98000.0}
      ]
    },
    "status": "ready"
  },
  "error": null
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `BAD_FILE` — not a `.csv`, empty, or unparseable |
| 413 | `FILE_TOO_LARGE` — over the ~100MB cap |
| 500 | `INGEST_FAILED` — DuckDB ingest error (message includes the reason) |

### `GET /datasets/{id}`

**Purpose:** Fetch a dataset's profile (re-open the profile card).

**Response (200):** same `data` shape as `POST /datasets` (id, name, row_count, columns, profile, status).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | `NOT_FOUND` — no such dataset |

### `POST /datasets/{id}/ask`

**Purpose:** Ask a natural-language question; run the agent (plan → DuckDB SQL → execute local → phrase) and return the answer + chart + summary table + the show-its-work trace.

**Request:**
```json
{ "question": "Which region had the highest total sales?" }
```

**Response (200, completed):**
```json
{
  "data": {
    "run_id": "uuid",
    "status": "completed",
    "answer": "The West region had the highest total sales at $4.2M.",
    "key_numbers": [{"label": "West total sales", "value": "$4.2M"}],
    "chart": {"type": "bar", "x": "region", "y": "total_sales",
              "data": [{"region": "West", "total_sales": 4200000}, {"region": "East", "total_sales": 3100000}]},
    "table": {"columns": ["region", "total_sales"],
              "rows": [["West", 4200000], ["East", 3100000]]},
    "plan": "Sum sales grouped by region, order descending, take the top.",
    "sql": "SELECT region, SUM(sales) AS total_sales FROM t GROUP BY region ORDER BY total_sales DESC",
    "trace": [
      {"step": "plan", "ok": true, "latency_ms": 820},
      {"step": "execute", "ok": true, "latency_ms": 140},
      {"step": "phrase", "ok": true, "latency_ms": 610}
    ],
    "cost_usd": 0.0021
  },
  "error": null
}
```

A trace with a recovered SQL error looks like:
```json
"trace": [
  {"step": "plan", "ok": true},
  {"step": "execute", "ok": false, "error": "Catalog Error: Scalar Function with name julianday does not exist"},
  {"step": "retry", "ok": true, "sql": "... date_diff('day', ...) ..."},
  {"step": "execute", "ok": true},
  {"step": "phrase", "ok": true}
]
```

**Response (200, failed):** `status="failed"`, `answer`/`chart`/`table` null, `error_message` set, `trace` still present (shows what was tried). The HTTP status is 200 — the failure is in the body so the UI can render the trace (mirrors the skeleton's "error in body, never swallowed" contract).

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | `NOT_FOUND` — no such dataset |
| 422 | `EMPTY_QUESTION` — blank question |
| 200 (body) | agent failure (LLM down, or SQL uncorrectable after retries) → `status="failed"`, `error_message` |

## Authentication

None — single local user, localhost only.
