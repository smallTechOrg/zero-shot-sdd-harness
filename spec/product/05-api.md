# API

## API Style

REST (FastAPI) + Server-rendered HTML (Jinja2). Browser UI is the primary surface.

## Endpoints

### `GET /`

**Purpose:** Data Sources home page — lists all DataSources with session counts and last activity.

**Response:** HTML

---

### `POST /datasources/upload`

**Purpose:** Accept a CSV file. Creates a `DataSource`, a `Tool`, and a `ToolCapability` (`run_query`) atomically.

**Request:** `multipart/form-data` with field `file` (CSV)

**Response:** Redirect to `GET /datasources/{id}`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | No file provided or file is not CSV |
| 500 | Disk write or DB insert failed |

---

### `GET /datasources/{datasource_id}`

**Purpose:** Show a DataSource's detail page: metadata, tools/capabilities, and list of sessions.

**Response:** HTML

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | DataSource not found |

---

### `POST /datasources/{datasource_id}/delete`

**Purpose:** Delete the DataSource and all related records (Tools, ToolCapabilities, Sessions, QueryRecords, AgentRuns) and the CSV file on disk.

**Response:** Redirect to `GET /`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | DataSource not found |

---

### `POST /datasources/{datasource_id}/sessions`

**Purpose:** Create a new Session for a DataSource.

**Request:** `application/x-www-form-urlencoded` — optional field `name`

**Response:** Redirect to `GET /sessions/{session_id}`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | DataSource not found |

---

### `GET /sessions/{session_id}`

**Purpose:** Show the session page: DataSource metadata, all past Q&A for this session (newest first), and the "Ask a question" form. Accepts `?new={query_record_id}` to highlight/scroll to a newly added answer.

**Response:** HTML

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Session not found |

---

### `POST /sessions/{session_id}/query`

**Purpose:** Submit a natural language question. Runs the LangGraph pipeline synchronously. On success, redirects to `GET /sessions/{session_id}?new={query_record_id}`.

**Request:** `application/x-www-form-urlencoded` with field `question`

**Response:** Redirect on success; renders `error.html` on pipeline failure

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Empty question |
| 404 | Session not found |
| 500 | Pipeline error — renders error.html with detail |

---

### `POST /sessions/{session_id}/delete`

**Purpose:** Delete a Session and all its QueryRecords and AgentRuns.

**Response:** Redirect to `GET /datasources/{datasource_id}`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Session not found |

---

### `GET /health`

**Purpose:** Health check — returns 200 with `{"status": "ok"}`.

**Response:**
```json
{"status": "ok"}
```

## Authentication

None in v0.1. Single-user local deployment.
