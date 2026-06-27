# API

FastAPI, single-origin, port **8001**. All responses use the baseline envelope: success → `{"data": ..., "error": null}` via `ok(data)`; errors → HTTP error with `{"detail": {"code": ..., "message": ...}}` via `api_error(code, message, status)`.

## `GET /health`

Baseline liveness check. Returns 200. (Unchanged from baseline.)

## `POST /datasets` — upload a data file

Multipart upload. Saves the file locally, parses it, builds the schema/profile.

**Request:** `multipart/form-data` with field `file` (the CSV; `.xlsx` accepted from Phase 2).

**Response** `ok(...)`:
```json
{
  "data": {
    "dataset_id": "uuid",
    "filename": "sales.csv",
    "file_format": "csv",
    "row_count": 1240,
    "column_count": 7,
    "columns": ["date", "region", "amount", "..."],
    "status": "ready"
  },
  "error": null
}
```

**Errors:**
| Code | When | Status |
|------|------|--------|
| `UNSUPPORTED_FORMAT` | extension not CSV (Phase 1) / not CSV-or-XLSX (Phase 2+) | 400 |
| `PARSE_FAILED` | pandas could not parse the file | 422 |
| `FILE_TOO_LARGE` | exceeds the configured row/byte cap | 413 |

> The raw file is stored locally; only its schema/profile is later sent to the LLM. The upload body never goes to any external service.

## `POST /analyses` — ask a question / run analysis

**Request** (`application/json`):
```json
{ "dataset_id": "uuid", "question": "What is the average amount per region?" }
```

Runs the LangGraph code-interpreter loop synchronously and returns the completed analysis.

**Response** `ok(...)`:
```json
{
  "data": {
    "analysis_id": "uuid",
    "dataset_id": "uuid",
    "question": "What is the average amount per region?",
    "status": "completed",
    "answer": "The average amount is highest in the West region (…) …",
    "code": "result = df.groupby('region')['amount'].mean()\nprint(result)",
    "steps": "region\nEast    102.4\nWest    188.1\n…",
    "result_value": "{'East': 102.4, 'West': 188.1, …}",
    "attempts": 1
  },
  "error": null
}
```

`code`, `steps`, and `answer` are always present on `status=completed`. On `status=failed`, `answer` holds a plain-language failure message, `error` describes the cause, and `code`/`steps` reflect the last attempt.

**Errors:**
| Code | When | Status |
|------|------|--------|
| `NOT_FOUND` | `dataset_id` unknown | 404 |
| `DATASET_NOT_READY` | dataset `status != ready` | 409 |
| `ANALYSIS_FAILED` | retries exhausted (also returned as `status=failed` body for graceful display — generator chooses 200-with-failed-body for the happy display path; reserve this code for unexpected failures) | 500 |

## `GET /analyses/{analysis_id}` — fetch a result

Returns the same shape as the `POST /analyses` response `data`. Used to re-fetch a completed analysis (answer + code + steps).

**Errors:** `NOT_FOUND` (404) if unknown.

---

## Surface ownership (for slicing)

- `POST /datasets` + `GET` dataset details → `src/api/datasets.py`
- `POST /analyses` + `GET /analyses/{id}` → `src/api/analyses.py`
- Router registration → `src/api/__init__.py` (serialized — shared file)
- Request/response Pydantic models → `src/domain/dataset.py`, `src/domain/analysis.py`

> Phase 1 implements all three POST/GET endpoints (upload, ask, fetch). No history-list endpoint in v1 (history is a deferred, stubbed feature).
