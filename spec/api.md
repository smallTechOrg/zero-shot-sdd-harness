# API

---

## API Style

REST/JSON over FastAPI, single-origin with the static UI at `/app`. Every response uses the skeleton envelope: success → `{"data": <payload>, "error": null}` (via `ok(...)`); failure → HTTP error with `{"detail": {"code", "message"}}` (via `api_error(...)`). No authentication (single local user).

Phase tags below mark which endpoints are **REAL in Phase 1** vs **added in Phase 2**. The UI shows Phase-2 features as labelled stubs until their endpoints land.

## Endpoints / Commands

### `POST /datasets`  *(Phase 1 — REAL)*

**Purpose:** upload a CSV/Excel file, profile it, store it, and return the profile card.

**Request:** `multipart/form-data` with a single `file` field (`.csv` or `.xlsx`).

**Response:**
```json
{
  "data": {
    "id": "uuid",
    "name": "sales_2024",
    "row_count": 50000,
    "column_count": 7,
    "file_format": "csv",
    "profile": {
      "columns": [
        {"name": "region", "dtype": "string", "null_count": 0, "sample_values": ["North", "South"]},
        {"name": "amount", "dtype": "float64", "null_count": 12, "sample_values": [10.5, 22.0]}
      ],
      "quality_flags": ["column 'amount' has 12 nulls (0.02%)"],
      "sample_rows": [{"region": "North", "amount": 10.5}]
    }
  },
  "error": null
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Missing file, unsupported extension, unparseable spreadsheet, or file over the size limit |
| 500 | Storage/profiling failure |

### `GET /datasets`  *(Phase 1 — REAL, minimal)*

**Purpose:** list uploaded datasets (id, name, row_count, created_at). Phase 1 renders the current dataset; the full library UI is a Phase-1 stub, but this endpoint is real.

**Response:** `{"data": [{"id", "name", "row_count", "column_count", "created_at"}], "error": null}`

### `GET /datasets/{id}`  *(Phase 1 — REAL)*

**Purpose:** fetch one dataset with its full profile (same `profile` shape as upload).

**Error cases:** `404` if the dataset id is unknown.

### `POST /runs`  *(Phase 1 — REAL)*

**Purpose:** ask a plain-language question about a dataset. Runs the agent synchronously and returns the full result.

**Request:**
```json
{ "dataset_id": "uuid", "question": "What were total sales by region?" }
```
> **Note:** this replaces the skeleton's `{"input_text": ...}` body. `session_id` is an optional field, ignored in Phase 1.

**Response:**
```json
{
  "data": {
    "run_id": "uuid",
    "dataset_id": "uuid",
    "status": "completed",
    "answer_text": "Total sales were $4.2M, led by the North region at $1.6M.",
    "narrative": "North and West together account for 68% of revenue...",
    "key_numbers": [{"label": "Total sales", "value": "$4.2M"}],
    "chart": { "$schema": "https://vega.github.io/schema/vega-lite/v5.json", "mark": "bar", "encoding": {"x": {"field": "region"}, "y": {"field": "amount"}}, "data": {"values": [{"region": "North", "amount": 1600000}]} },
    "table": [{"region": "North", "amount": 1600000}],
    "code": "result = {\"value\": None, \"table\": df.groupby('region')['amount'].sum().reset_index().to_dict('records'), \"columns\": [\"region\",\"amount\"]}",
    "attempts": 1,
    "error": null
  },
  "error": null
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Missing `dataset_id`/`question` |
| 404 | Unknown `dataset_id` |
| 200 with `status="failed"` + `error` | Agent failed after bounded retries or an LLM error — surfaced in the body, never silently swallowed |

### `GET /runs/{id}`  *(Phase 1 — REAL)*

**Purpose:** fetch a saved run (same payload as `POST /runs`). Backs the Phase-2 history detail view; real in Phase 1 for re-fetch.

**Error cases:** `404` if unknown.

### `GET /health`  *(exists)*

Returns `{"data": {"status": "ok"}, "error": null}`.

---

### Phase 2 endpoints  *(added later — UI stubs until then)*

| Endpoint | Purpose |
|----------|---------|
| `POST /sessions`, `GET /sessions/{id}` | Create/fetch a session; threads conversation memory into follow-up questions |
| `GET /runs?dataset_id=&session_id=` | List history (revisitable) |
| `POST /runs/{id}/rerun` | Re-run a saved question against the current data (creates a new run) |
| `POST /cost/estimate` | Pre-flight token/cost estimate + expensive-run warning for a question |
| `GET /runs/{id}/progress` (SSE) | Live step-progress stream: "Planning… / Running code… / Retrying… / Writing answer…" |

## Authentication

None. Single local user on `localhost`; no tokens, no sessions-as-auth.
