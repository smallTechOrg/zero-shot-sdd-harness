# API

## API Style

REST over HTTP. JSON request/response bodies (except for the multipart file upload endpoint). All endpoints are prefixed with `/api`. The FastAPI app also serves the frontend at `/` (static HTML).

## Endpoints / Commands

---

### `POST /api/uploads`

**Purpose:** Accept a CSV file upload, parse it, persist metadata to SQLite, save the file to disk, and return the upload record.

**Request:** `multipart/form-data` with a single field named `file`.

```
Content-Type: multipart/form-data
file: <binary CSV content>
```

**Response:**
```json
{
  "id": "3f2a1c08-84e1-4b2d-a9f0-e2c7b5d61234",
  "filename": "3f2a1c08-84e1-4b2d-a9f0-e2c7b5d61234.csv",
  "original_filename": "sales_q1.csv",
  "row_count": 312,
  "columns": ["date", "region", "product", "amount"],
  "uploaded_at": "2026-06-14T10:23:45Z"
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | No file provided in the request |
| 422 | File is not a valid CSV (parse error from pandas) |
| 422 | File is empty (0 data rows) |
| 500 | Disk write failure or database error |

---

### `GET /api/uploads/{id}`

**Purpose:** Retrieve metadata for a previously uploaded CSV by its UUID.

**Request:** No body. `id` is a path parameter (UUID string).

**Response:**
```json
{
  "id": "3f2a1c08-84e1-4b2d-a9f0-e2c7b5d61234",
  "filename": "3f2a1c08-84e1-4b2d-a9f0-e2c7b5d61234.csv",
  "original_filename": "sales_q1.csv",
  "row_count": 312,
  "columns": ["date", "region", "product", "amount"],
  "uploaded_at": "2026-06-14T10:23:45Z"
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No upload found with the given `id` |

---

### `POST /api/queries`

**Purpose:** Accept a natural-language question about an uploaded CSV, call Gemini with a context prompt, persist the question and answer, and return the result.

**Request:**
```json
{
  "upload_id": "3f2a1c08-84e1-4b2d-a9f0-e2c7b5d61234",
  "question": "What is the total sales amount for the West region?"
}
```

**Response:**
```json
{
  "id": "a9c3b2d1-ff01-4e5a-b123-789abc012345",
  "upload_id": "3f2a1c08-84e1-4b2d-a9f0-e2c7b5d61234",
  "question": "What is the total sales amount for the West region?",
  "answer": "Based on the data provided, the total sales amount for the West region is $48,230.",
  "created_at": "2026-06-14T10:25:10Z"
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `question` is empty or whitespace-only |
| 404 | `upload_id` does not match any upload record |
| 422 | Request body missing required fields |
| 503 | Gemini API key not configured (`GEMINI_API_KEY` env var absent or empty) |
| 503 | Gemini API returned an error or quota exceeded |
| 500 | CSV file missing from disk or database error |

---

### `GET /api/queries/{id}`

**Purpose:** Retrieve a previously submitted query and its answer by UUID.

**Request:** No body. `id` is a path parameter (UUID string).

**Response:**
```json
{
  "id": "a9c3b2d1-ff01-4e5a-b123-789abc012345",
  "upload_id": "3f2a1c08-84e1-4b2d-a9f0-e2c7b5d61234",
  "question": "What is the total sales amount for the West region?",
  "answer": "Based on the data provided, the total sales amount for the West region is $48,230.",
  "created_at": "2026-06-14T10:25:10Z"
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | No query found with the given `id` |

---

## Authentication

None in v0.1. The API is unauthenticated and intended for localhost use only. All endpoints are publicly accessible on whatever port uvicorn is bound to. Do not expose this server on a public network without adding authentication in a later phase.
