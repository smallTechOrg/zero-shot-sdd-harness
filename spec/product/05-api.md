# API

## API Style

REST over HTTP/JSON. File upload uses `multipart/form-data`. All other endpoints use `application/json`. The base path is `/api`. The API is served by FastAPI on `localhost:8000` in development.

## Endpoints

---

### `POST /api/sessions`

**Purpose:** Upload a data file and create a new session. Returns the session ID and parsed dataset metadata.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | yes | The CSV or JSON file to upload. Max 50 MB. |

**Response:** `201 Created`
```json
{
  "session_id": "3f8a2b1c-...",
  "filename": "sales_data.csv",
  "row_count": 4820,
  "column_names": ["date", "region", "product", "amount"],
  "column_dtypes": {
    "date": "object",
    "region": "object",
    "product": "object",
    "amount": "float64"
  },
  "created_at": "2026-06-18T10:00:00Z"
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | No file provided in request |
| 415 | File extension is not `.csv` or `.json` |
| 413 | File size exceeds 50 MB |
| 422 | File could not be parsed by pandas (malformed CSV/JSON) |
| 500 | Internal server error (disk write failure, SQLite error) |

---

### `GET /api/sessions/{session_id}`

**Purpose:** Retrieve metadata for an existing session, including column schema and status.

**Path parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string (UUID4) | The session to retrieve |

**Response:** `200 OK`
```json
{
  "session_id": "3f8a2b1c-...",
  "filename": "sales_data.csv",
  "file_size_bytes": 2048000,
  "row_count": 4820,
  "column_names": ["date", "region", "product", "amount"],
  "column_dtypes": {
    "date": "object",
    "region": "object",
    "product": "object",
    "amount": "float64"
  },
  "status": "ready",
  "created_at": "2026-06-18T10:00:00Z",
  "last_active_at": "2026-06-18T10:05:00Z"
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | `session_id` does not exist in SQLite |
| 500 | Internal server error |

---

### `GET /api/sessions/{session_id}/messages`

**Purpose:** Retrieve the full chat history for a session, ordered oldest-first.

**Path parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string (UUID4) | The session whose messages to retrieve |

**Response:** `200 OK`
```json
{
  "session_id": "3f8a2b1c-...",
  "messages": [
    {
      "id": "a1b2c3d4-...",
      "role": "user",
      "content": "What is the average amount by region?",
      "reasoning_trace": null,
      "iteration_count": null,
      "created_at": "2026-06-18T10:01:00Z"
    },
    {
      "id": "e5f6a7b8-...",
      "role": "assistant",
      "content": "The average amount by region is: North: 1240.5, South: 980.2, West: 1105.8.",
      "reasoning_trace": [
        {"type": "think", "content": "I need to group by 'region' and compute the mean of 'amount'."},
        {"type": "action", "content": "df.groupby('region')['amount'].mean()"},
        {"type": "observe", "content": "region\nNorth    1240.5\nSouth     980.2\nWest     1105.8\nName: amount, dtype: float64"}
      ],
      "iteration_count": 1,
      "created_at": "2026-06-18T10:01:08Z"
    }
  ]
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | `session_id` does not exist |
| 500 | Internal server error |

---

### `POST /api/sessions/{session_id}/messages`

**Purpose:** Send a question to the ReAct agent and receive an answer grounded in the uploaded dataset.

**Path parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string (UUID4) | The session to query |

**Request:** `application/json`
```json
{
  "question": "Which product had the highest total amount?"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | yes | Plain-English question about the uploaded data. Max 2000 characters. |

**Response:** `200 OK`
```json
{
  "message_id": "e5f6a7b8-...",
  "answer": "The product with the highest total amount is 'Widget Pro' with a total of $48,320.",
  "reasoning_trace": [
    {"type": "think", "content": "I need to group by 'product' and sum 'amount', then find the max."},
    {"type": "action", "content": "df.groupby('product')['amount'].sum().idxmax()"},
    {"type": "observe", "content": "'Widget Pro'"},
    {"type": "action", "content": "df.groupby('product')['amount'].sum().max()"},
    {"type": "observe", "content": "48320.0"}
  ],
  "iteration_count": 2,
  "created_at": "2026-06-18T10:06:00Z"
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `question` field missing or empty |
| 404 | `session_id` does not exist |
| 410 | Session's DataFrame is no longer in memory (server was restarted); client should re-upload |
| 422 | `question` exceeds 2000 characters |
| 503 | Gemini API returned an error or timed out |
| 500 | Internal server error |

> **Assumed:** The `410 Gone` response is used when the session record exists in SQLite but the DataFrame is no longer in the in-memory cache (server restart). The client should show a "Please re-upload your file to continue" message.

---

## Authentication

None in v0.1. The API has no authentication layer — all endpoints are open. The API is only accessible on `localhost` in the local development deployment.

> **Assumed:** A future phase targeting cloud deployment will add an API key header or session token for basic access control. For v0.1, network-level isolation (localhost only) is the sole protection.
