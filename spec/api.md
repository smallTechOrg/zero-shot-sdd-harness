# API

## API Style

REST over HTTP. All responses use the envelope `{ "data": <payload>, "error": null }` on success. HTTP errors use `{ "detail": { "code": "...", "message": "..." } }`. The analysis call is synchronous — `POST /analyses` blocks until the full pipeline completes and returns the result directly (no polling, no WebSocket).

## Authentication

No authentication. Personal-use local tool; the server binds to `localhost:8001` and is not exposed to a network.

---

## Endpoints

### `POST /datasets`

**Purpose:** Upload a CSV file. Stores the file to `data/uploads/<uuid>.csv`, computes metadata, persists a `DatasetRow`, and returns the dataset ID for use in subsequent analysis calls.

**Request:** `multipart/form-data` with field `file` (the CSV file).

**Response 200:**
```json
{
  "data": {
    "dataset_id": "3f2a1b4c-...",
    "filename": "sales_q1.csv",
    "row_count": 1200,
    "column_names": ["date", "revenue", "region", "product"]
  },
  "error": null
}
```

**Error cases:**
| Status | Code | Condition |
|---|---|---|
| 413 | `FILE_TOO_LARGE` | File exceeds 50 MB |
| 400 | `INVALID_CSV` | File cannot be parsed as CSV by pandas |
| 500 | `UPLOAD_FAILED` | Filesystem write error |

---

### `GET /datasets`

**Purpose:** List all uploaded datasets (most recent first).

**Response 200:**
```json
{
  "data": [
    {
      "dataset_id": "3f2a1b4c-...",
      "filename": "sales_q1.csv",
      "row_count": 1200,
      "column_names": ["date", "revenue", "region"],
      "uploaded_at": "2026-06-27T10:00:00Z"
    }
  ],
  "error": null
}
```

---

### `POST /analyses`

**Purpose:** Run the full analysis pipeline against an uploaded dataset. Blocks until complete. Returns the plain-English answer and the Plotly chart JSON.

**Request:**
```json
{
  "dataset_id": "3f2a1b4c-...",
  "question": "What is the average revenue by region?"
}
```

**Response 200 (success):**
```json
{
  "data": {
    "analysis_id": "9d8e7f6a-...",
    "dataset_id": "3f2a1b4c-...",
    "question": "What is the average revenue by region?",
    "answer_text": "The average revenue is highest in the North region at $42,300, followed by South at $38,100 and West at $31,700.",
    "chart_json": "{\"data\": [{\"type\": \"bar\", \"x\": [\"North\", \"South\", \"West\"], \"y\": [42300, 38100, 31700]}], \"layout\": {\"title\": \"Average Revenue by Region\"}}",
    "status": "completed",
    "error": null
  },
  "error": null
}
```

**Response 200 (agent failure — not a 5xx):**
```json
{
  "data": {
    "analysis_id": "9d8e7f6a-...",
    "dataset_id": "3f2a1b4c-...",
    "question": "...",
    "answer_text": null,
    "chart_json": null,
    "status": "failed",
    "error": "Gemini API returned non-JSON plan after retry"
  },
  "error": null
}
```

**Error cases:**
| Status | Code | Condition |
|---|---|---|
| 400 | `DATASET_NOT_FOUND` | `dataset_id` does not exist in the `datasets` table |
| 400 | `EMPTY_QUESTION` | `question` is blank or whitespace-only |

---

### `GET /analyses/{analysis_id}`

**Purpose:** Retrieve a previously computed analysis by ID.

**Response 200:**
```json
{
  "data": {
    "analysis_id": "9d8e7f6a-...",
    "dataset_id": "3f2a1b4c-...",
    "question": "What is the average revenue by region?",
    "answer_text": "...",
    "chart_json": "...",
    "status": "completed",
    "error": null
  },
  "error": null
}
```

**Error cases:**
| Status | Code | Condition |
|---|---|---|
| 404 | `ANALYSIS_NOT_FOUND` | `analysis_id` does not exist |

---

### `GET /health`

**Purpose:** Health check (existing skeleton route, retained).

**Response 200:** `{ "status": "ok" }`

---

### `POST /runs` (legacy — retained)

The existing skeleton's text-transform route. Retained for backward compatibility with existing tests. Not used by the new analysis UI.

---

## Notes

- `chart_json` is a string containing a valid Plotly figure JSON object. The frontend parses it with `JSON.parse()` and passes the result to `Plotly.react()`. A null value means no chart was generated; the frontend shows only the text answer.
- `POST /analyses` is synchronous and may take 5–15 seconds. The frontend shows a loading state (spinner + "Analyzing…" label) during this time.
- File uploads use `python-multipart` (required FastAPI dependency for `multipart/form-data`); it must be declared in `pyproject.toml` `[project.dependencies]`.
