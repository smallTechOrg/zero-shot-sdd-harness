# API

## API Style

REST (FastAPI) + server-rendered HTML (Jinja2) for the browser UI, **plus** an MCP **JSON-RPC 2.0**
endpoint (`POST /mcpserver/{id}`) implementing the MCP 2025-06-18 tools/resources/prompts protocol.

The three primary entities each own an `api/` module: `mcpserver.py`, `sessions.py`, `queries.py`
(`home.py` + `health.py` are support routes).

## Endpoints

### `GET /`

**Purpose:** Home page — lists all MCP servers (name, title, type, table count, version, last-sync
status, credential-free URI) and all sessions, side by side.
**Response:** HTML

---

### `POST /mcpserver/upload`  (auxiliary)

**Purpose:** Convert a CSV to Parquet under a named dataset directory and return its data URI. Creates the
directory if absent. **Creates no entity** — it is the file-staging step the UI calls before
`POST /mcpserver` (new dataset) or, in Phase B, `resources/add` (existing dataset).

**Request:** `multipart/form-data` — `dataset_name` (required), `file` (CSV/XLSX/JSON, required)
**Response:** JSON `{"uri": "parquet:///{name}", "table": "<table_name>"}`

| Status | Condition |
|--------|-----------|
| 400 | Missing `dataset_name` or `file`; unsupported type; parse/convert failed |
| 500 | Disk write failed |

---

### `POST /mcpserver`

**Purpose:** Create an MCP server from a dataset URI + type. Enforces **1:1 dataset↔server** (rejects a
duplicate `uri` or `name`). Reads the dataset (parquet: the directory; external: introspection) to build
`physical_tables_json`, runs **`connection_check()` before commit** (a broken server is never persisted),
inserts the `McpServer` row (version 1), then runs the **sync pipeline** to generate its
tools/resources/prompts.

- **Internal (parquet, default):** `dataset_uri = parquet:///{name}` (from a prior `/upload`). The
  dataset directory's Parquet files become the physical tables.
- **External (postgresql, BETA):** `dataset_uri = postgresql://…`. Gated by
  `DATAANALYSIS_ENABLE_EXTERNAL_DATASETS` (default off → 501).

**Request:** `application/x-www-form-urlencoded` or JSON — `dataset_uri` (required), `dataset_type`
(`parquet` (default) | `postgresql`), `name` (optional; defaults to the URI's database name)
**Response:** Redirect to `GET /` (form) or JSON `{server}` (API)

| Status | Condition |
|--------|-----------|
| 400 | Missing/duplicate `name`/`uri`; dataset dir empty/unreadable; `connection_check()` failed (credential-free message) |
| 501 | External `dataset_type` while the flag is off |
| 500 | Unexpected error |

---

### `POST /mcpserver/{id}/sync`

**Purpose:** Re-run the 5-stage LLM sync pipeline against the dataset and the **existing** capabilities,
then **transactionally apply** the result: match→update, new→insert, missing→**soft-delete** (never hard
delete); bump `version`; set title/description/`dataset_schema_json`/`last_synced_at`/`last_sync_status`.
Closes the pools of sessions attached to this server. *(The user originally specified `GET`; this is a
mutation that bumps version, so it is `POST`.)*

**Response:** Redirect to `GET /` (form) or JSON `{server, version}` (API)

| Status | Condition |
|--------|-----------|
| 404 | Server not found |
| 400 | `connection_check()` failed (parquet file missing / external connect failed — credential-free) |

---

### `POST /mcpserver/{id}`  — MCP JSON-RPC 2.0 dispatch

**Purpose:** The standards-compliant MCP surface over the server's stored capability rows. A single
endpoint dispatching on `method`. Request: `{"jsonrpc":"2.0","id":…,"method":"…","params":{…}}`.

**Read methods (Phase A):**

| Method | Params | Result |
|--------|--------|--------|
| `tools/list` | `{cursor?}` | `{tools:[{name,title?,description,inputSchema,outputSchema?,annotations?}], nextCursor?}` |
| `tools/call` | `{name, arguments}` | `CallToolResult {content:[{type:"text",text}], structuredContent?, isError}` |
| `resources/list` | `{cursor?}` | `{resources:[{uri,name,title?,description,mimeType}], nextCursor?}` |
| `resources/read` | `{uri}` | `{contents:[{uri,mimeType,text}]}` |
| `prompts/list` | `{cursor?}` | `{prompts:[{name,title?,description,arguments}], nextCursor?}` |
| `prompts/get` | `{name, arguments?}` | `{description, messages:[…]}` |

- **`tools/call`** binds `arguments` into the tool's `sql_template` via DuckDB **parameter binding** and
  runs it through the read-only SELECT guard. Query/SQL failures → `isError:true` in the **result**
  (not a JSON-RPC error). Unknown tool `name` → JSON-RPC error `-32602`.
- **Pagination:** opaque keyset `cursor` (base64 of the last `(created_at, id)`); `nextCursor` is omitted
  on the last page; a malformed/forged cursor → `-32602`. Page size = `mcp_list_page_size` (default 50).
- **Errors:** unknown `method` → `-32601`; invalid params/cursor → `-32602`; tool-execution failures use
  `isError:true`. Capabilities are filtered to **active** rows (`deleted_at IS NULL`).

**Mutation methods (Phase B — specced in capability 4, not implemented yet):** `tools/add`,
`tools/update`, `prompts/add`, `prompts/update`, `resources/add`, `resources/update`. Adding/updating a
**resource** triggers a partial sync of **tools + prompts**; adding/updating a **tool** triggers a partial
sync of **prompts**; prompt changes have no cascade. Until implemented, these return `-32601`.

---

### `GET /mcpserver/{id}`

**Purpose:** Server detail page — metadata (title, type, credential-free URI, version, last-sync status),
the dataset's physical tables/schema, and the active tools/resources/prompts lists, with a **Sync** button.
**Response:** HTML — 404 if not found.

---

### `POST /mcpserver/{id}/delete`

**Purpose:** Delete the server (unlinking sessions, cascading capability rows) and remove the dataset
directory on disk.
**Response:** Redirect to `GET /` — 404 if not found.

---

### `POST /sessions`

**Purpose:** Create a session over one or more MCP servers.
**Request:** `application/x-www-form-urlencoded` — `name` (optional), `mcp_server_ids` (≥1 required)
**Response:** Redirect to `GET /sessions/{session_id}`

| Status | Condition |
|--------|-----------|
| 400 | No server selected |
| 404 | A referenced server not found |

---

### `GET /sessions/{session_id}`

**Purpose:** Session page — attached servers (name + table count), all past Q&A (newest first), the
"Ask a question" form. Accepts `?new={query_record_id}` to highlight a new answer.
**Response:** HTML — 404 if not found.

---

### `POST /sessions/{session_id}/query`

**Purpose:** Submit an NL question. Creates the QueryRecord + AgentRun and runs the LangGraph MCP pipeline
on a background daemon thread. Redirects to `GET /sessions/{session_id}?new={query_record_id}`.
**Request:** `application/x-www-form-urlencoded` — `question`

| Status | Condition |
|--------|-----------|
| 400 | Empty question |
| 404 | Session not found |
| 500 | Pipeline error — renders error.html with detail |

---

### `POST /sessions/{session_id}/delete`

**Purpose:** Close the session's pool, then delete the Session + its QueryRecords + AgentRuns.
**Response:** Redirect to `GET /` — 404 if not found.

---

### `GET /health`

**Purpose:** Health check — 200 `{"status": "ok"}`.

## Authentication

None in v0.1. Single-user local deployment.
