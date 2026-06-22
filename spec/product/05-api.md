# API

> **Spec status:** Filled in for the **Senior Data Analyst Agent** (`data-analyst`), v0.1. Last updated 2026-06-22. The UI (server-rendered pages) is described in `06-ui.md`; this file lists the HTTP surface.

---

## API Style

**REST-ish HTTP over FastAPI**, serving both JSON endpoints and a small set of server-rendered HTML pages. Single local user; no auth in v0.1.

## Endpoints / Commands

### `GET /health`

**Purpose:** Liveness check; also reports whether the LLM provider is real or stub.

**Response:**
```json
{ "status": "ok", "llm_provider": "real | stub" }
```

---

### `POST /sessions`

**Purpose:** Create a new session.

**Request:**
```json
{ "name": "string — human label for the session" }
```

**Response:**
```json
{ "id": 1, "name": "Q2 billing review", "created_at": "2026-06-22T10:00:00Z" }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Missing/empty name |
| 500 | Metadata DB write failure |

---

### `GET /sessions`

**Purpose:** List all sessions (so a user can reopen one after restart).

**Response:**
```json
{ "sessions": [ { "id": 1, "name": "Q2 billing review", "updated_at": "..." } ] }
```

---

### `POST /sessions/{session_id}/datasets`

**Purpose:** Upload and register a CSV/Parquet file as a dataset (capability 01). `multipart/form-data`.

**Request:** form fields — `file` (the upload, required), `name` (optional display name).

**Response:**
```json
{
  "id": 7,
  "session_id": 1,
  "name": "invoices",
  "file_format": "csv",
  "duckdb_table": "s1_invoices",
  "row_count": 4821,
  "schema": [ { "name": "amount", "type": "DECIMAL" } ]
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Unsupported format / unparseable file |
| 404 | Session not found |
| 500 | Ingestion or metadata write failure (ingest rolled back; failure audited) |

---

### `GET /sessions/{session_id}/datasets`

**Purpose:** List the datasets registered in a session (capability 01).

**Response:**
```json
{ "datasets": [ { "id": 7, "name": "invoices", "row_count": 4821, "file_format": "csv" } ] }
```

**Error cases:** `404` session not found.

---

### `POST /sessions/{session_id}/ask`

**Purpose:** Ask a natural-language question over the session's datasets; runs the agent (capability 02).

**Request:**
```json
{ "question": "What was total invoiced revenue per customer tier last month?" }
```

**Response:**
```json
{
  "message_id": 42,
  "answer_text": "Tier A invoiced $1.2M, Tier B $480K, Tier C $90K last month.",
  "generated_sql": "SELECT tier, SUM(amount) ... GROUP BY tier",
  "result_table": { "columns": ["tier","total"], "rows": [["A",1200000],["B",480000]] },
  "audit_entry_id": 99
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Empty question, or session has no datasets |
| 404 | Session not found |
| 200 + error payload | Agent ran but failed (bad SQL after retry / LLM error): returns a friendly `answer_text` describing the failure; an `error` audit entry is written. The app does not 500 on agent-internal failures. |

---

### `GET /sessions/{session_id}/audit`

**Purpose:** View the audit log for a session, newest first (capability 03).

**Response:**
```json
{
  "entries": [
    {
      "id": 99, "nl_prompt": "What was total invoiced revenue...",
      "generated_sql": "SELECT ...", "row_count": 3, "duration_ms": 128,
      "status": "success", "created_at": "2026-06-22T10:05:00Z"
    }
  ]
}
```

**Error cases:** `404` session not found.

---

## Web Pages (server-rendered — see `06-ui.md`)

| Route | Purpose |
|-------|---------|
| `GET /` | Home: list/create sessions |
| `GET /sessions/{session_id}` | Session view: datasets + upload (left), chat (center), audit panel |

## Authentication

**None in v0.1.** Single local user on a local machine. The Gemini API key (env `DATA_ANALYST_GEMINI_API_KEY`) is read from the environment (a secret), never exposed via any endpoint.
