# Data Model

## Storage Technology

**SQLite** — a single file-based relational database stored at `./data/datachat.db`. SQLite is chosen because:
- v0.1 is single-user with no concurrent write contention.
- No external database server is required, keeping local setup trivial.
- The full schema fits in two small tables.

In-memory state (parsed DataFrames) is held in a process-level Python dict keyed by `session_id`. This is not persisted to SQLite; if the server restarts, the user must re-upload their file. Chat history is fully persisted and survives restarts.

## Entities

### Entity: Session

Represents one user upload session. Created when a file is successfully uploaded. A session is the container for one file and all chat messages about that file.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID4) | yes | Primary key — the `session_id` shared with the client |
| filename | TEXT | yes | Original filename as uploaded by the user |
| file_path | TEXT | yes | Absolute path to the raw file on disk (`/tmp/datachat/<id>/filename`) |
| file_size_bytes | INTEGER | yes | File size in bytes at upload time |
| row_count | INTEGER | yes | Number of rows in the parsed DataFrame |
| column_names | TEXT (JSON array) | yes | Serialized list of column name strings |
| column_dtypes | TEXT (JSON object) | yes | Serialized map of column name → pandas dtype string |
| status | TEXT | yes | `"ready"` \| `"error"` — whether the file was parsed successfully |
| error_message | TEXT | no | Populated if `status = "error"`; human-readable parse error |
| created_at | TEXT (ISO-8601) | yes | UTC timestamp when the session was created |
| last_active_at | TEXT (ISO-8601) | yes | UTC timestamp of the most recent chat message |

### Entity: Message

Represents one turn in the chat conversation within a session. Each user question and each agent answer are stored as separate rows, ordered by `created_at`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | TEXT (UUID4) | yes | Primary key |
| session_id | TEXT (UUID4) | yes | Foreign key → `Session.id` |
| role | TEXT | yes | `"user"` \| `"assistant"` |
| content | TEXT | yes | The message text (question or answer) |
| reasoning_trace | TEXT (JSON array) | no | Populated for `role = "assistant"` only; ordered list of ReAct steps (`{type, content}`) |
| iteration_count | INTEGER | no | Number of ReAct loop iterations used to produce this answer |
| created_at | TEXT (ISO-8601) | yes | UTC timestamp when the message was created |

### Relationships

```
Session (1) ──────── (many) Message
   id ──────────────── session_id (FK)
```

One session has zero or more messages. Messages are never shared across sessions. Deleting a session cascades to delete all its messages.

## Data Lifecycle

| Event | Action |
|-------|--------|
| File uploaded successfully | New `Session` row created with `status = "ready"` |
| File fails to parse | New `Session` row created with `status = "error"` and `error_message` set |
| User sends a question | New `Message` row with `role = "user"` inserted; `Session.last_active_at` updated |
| Agent produces an answer | New `Message` row with `role = "assistant"` inserted |
| Server restart | `Session` and `Message` rows survive (in SQLite); in-memory DataFrame cache is cleared — user must re-upload to chat again |
| Session cleanup | Not implemented in v0.1. Future phase: purge sessions older than 7 days and delete associated temp files. |

> **Assumed:** There is no automatic session expiry or cleanup in v0.1. Sessions and messages accumulate indefinitely in the SQLite file. A future phase will add a TTL-based cleanup job.

## Sensitive Data

| Field | Sensitivity | Protection |
|-------|------------|------------|
| Uploaded file contents | Potentially sensitive (user's own data) | Stored only on local disk in `/tmp/`; not logged; not sent anywhere except to the Gemini API as part of query context |
| `GEMINI_API_KEY` | Secret | Stored in `.env` file only; never logged, never returned in any API response; `.env` is in `.gitignore` |
| `column_names`, `column_dtypes` | Low — structural metadata only | Stored in SQLite; no special protection in v0.1 |
| `content` (Message) | Potentially sensitive (user questions about their data) | Stored in local SQLite only; not transmitted externally except as conversation context to Gemini |

> **Assumed:** No encryption at rest for the SQLite file or temp files in v0.1. This is acceptable for a local, single-user development deployment. A future phase targeting cloud deployment must add encryption at rest and proper secret management.
