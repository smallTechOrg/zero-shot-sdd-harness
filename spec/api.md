# API

## API Style

REST. All endpoints return a JSON envelope:
- Success: `{"data": <payload>, "error": null}`
- Failure: `{"data": null, "error": {"code": "ERROR_CODE", "message": "Human-readable message"}}`

All timestamps are ISO 8601 UTC strings.

---

## Endpoints

### `POST /sessions`

**Purpose:** Create a new analysis session. Must be called before uploading files or sending messages.

**Request:** No body required.

**Response 200:**
```json
{
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "created_at": "2026-06-29T12:00:00Z"
  },
  "error": null
}
```

**Error cases:**

| Status | Code | Condition |
|--------|------|-----------|
| 500 | INTERNAL_ERROR | SQLite write failed |

---

### `POST /sessions/{session_id}/files`

**Purpose:** Upload a CSV file into the session. Triggers automatic profiling (no LLM call). Returns a full profile card.

**Request:** `multipart/form-data` with field `file` containing the CSV file binary.

**Response 200:**
```json
{
  "data": {
    "file_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "filename": "sales.csv",
    "profile": {
      "row_count": 1250,
      "column_count": 8,
      "columns": [
        {
          "name": "revenue",
          "dtype": "float64",
          "null_count": 3,
          "null_pct": 0.24,
          "stats": {
            "min": 0.0,
            "max": 99999.9,
            "mean": 5432.1,
            "std": 3210.5,
            "p25": 1200.0,
            "p50": 4800.0,
            "p75": 8900.0
          },
          "sample_values": ["1200.0", "8450.5", "320.0"]
        },
        {
          "name": "region",
          "dtype": "object",
          "null_count": 0,
          "null_pct": 0.0,
          "top_values": {"West": 340, "East": 310, "North": 300, "South": 300},
          "sample_values": ["West", "East", "North"]
        }
      ],
      "quality_flags": [
        {"type": "WARNING", "column": "revenue", "message": "3 null values (0.24%)"},
        {"type": "WARNING", "column": null, "message": "42 duplicate rows detected"}
      ]
    }
  },
  "error": null
}
```

**Error cases:**

| Status | Code | Condition |
|--------|------|-----------|
| 400 | INVALID_FILE | Uploaded file is not a CSV (wrong extension or unreadable by pandas) |
| 404 | SESSION_NOT_FOUND | session_id does not exist in the sessions table |
| 500 | PROFILING_FAILED | pandas profiling raised an unexpected exception |

---

### `POST /sessions/{session_id}/messages`

**Purpose:** Send a natural-language question. Runs the full Q&A pipeline (plan_and_code → execute_code → format_response). Returns the assistant's prose answer and an optional Plotly chart.

**Request:**
```json
{
  "content": "Show me a bar chart of revenue by region"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| content | string | yes | The user's natural-language question (max 2000 characters) |

**Response 200:**
```json
{
  "data": {
    "message_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "role": "assistant",
    "content": "Revenue by region shows the West leading at $2.1M, followed by East at $1.8M, North at $1.5M, and South at $1.4M.",
    "chart_json": {
      "data": [
        {
          "type": "bar",
          "x": ["West", "East", "North", "South"],
          "y": [2100000, 1800000, 1500000, 1400000]
        }
      ],
      "layout": {
        "title": "Revenue by Region",
        "xaxis": {"title": "Region"},
        "yaxis": {"title": "Revenue ($)"}
      }
    },
    "created_at": "2026-06-29T12:05:00Z"
  },
  "error": null
}
```

`chart_json` is `null` when the generated code did not produce a Plotly figure.

**Error cases:**

| Status | Code | Condition |
|--------|------|-----------|
| 400 | NO_FILES | No files have been uploaded to this session yet |
| 400 | EMPTY_CONTENT | content field is missing or blank |
| 404 | SESSION_NOT_FOUND | session_id does not exist |
| 422 | VALIDATION_ERROR | Request body fails schema validation |
| 500 | AGENT_ERROR | LLM call or code execution failed (error surfaced in content field of response, not as HTTP 500) |

> **Note:** Agent errors (Gemini failures, exec() exceptions) are returned as HTTP 200 with the error message in the `content` field of the assistant message, not as HTTP 5xx. Only unexpected server-level errors return 500.

---

### `GET /sessions/{session_id}/messages`

**Purpose:** Retrieve the full conversation history for a session in chronological order.

**Request:** No body. No query parameters in Phase 1.

**Response 200:**
```json
{
  "data": {
    "messages": [
      {
        "message_id": "aaa85f64-5717-4562-b3fc-2c963f66afa6",
        "role": "user",
        "content": "Show me a bar chart of revenue by region",
        "chart_json": null,
        "created_at": "2026-06-29T12:04:55Z"
      },
      {
        "message_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "role": "assistant",
        "content": "Revenue by region shows the West leading at $2.1M...",
        "chart_json": {"data": [...], "layout": {...}},
        "created_at": "2026-06-29T12:05:00Z"
      }
    ]
  },
  "error": null
}
```

**Error cases:**

| Status | Code | Condition |
|--------|------|-----------|
| 404 | SESSION_NOT_FOUND | session_id does not exist |

---

### `DELETE /sessions/{session_id}`

**Purpose:** Delete a session and all associated data: messages, uploaded file records, and temp CSV files from disk.

**Request:** No body.

**Response 200:**
```json
{
  "data": {"deleted": true},
  "error": null
}
```

**Error cases:**

| Status | Code | Condition |
|--------|------|-----------|
| 404 | SESSION_NOT_FOUND | session_id does not exist |

---

### `GET /app/*` (Static Frontend)

**Purpose:** Serve the built Next.js static export from `frontend/out/`. FastAPI mounts this via `StaticFiles`.

**Response:** HTML/CSS/JS files. Returns 404 if the frontend has not been built yet.

---

## Authentication

No authentication in Phase 1. Session IDs are UUID v4 values (128-bit random) which act as opaque access tokens — sufficiently unguessable for a single-user personal tool. All session data is ephemeral and session-scoped.

---

## Error Envelope

All errors use this shape:

```json
{
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description of the problem"
  }
}
```

Error codes are SCREAMING_SNAKE_CASE strings. The `message` field is safe to display to the user.
