# Capability 03 — Session Management

## What It Does

Creates and persists upload sessions in SQLite, stores each chat message (user and assistant) as it occurs, and retrieves full session metadata and conversation history on demand. This capability is the persistence backbone that allows chat history to survive page refreshes and server restarts (with the exception of the in-memory DataFrame, which must be re-uploaded after a restart).

## Inputs

| Input | Source | Description |
|-------|--------|-------------|
| `session_id` | URL path parameter | UUID4 identifying the session |
| Session metadata | File Upload capability | filename, file path, row count, column names, dtypes, status |
| User message | Data Chat capability / `POST /api/sessions/{id}/messages` | Question text from the user |
| Assistant message | Data Chat capability (after ReAct loop) | Answer text, reasoning trace, iteration count |

## Outputs

| Output | Destination | Description |
|--------|-------------|-------------|
| Session record (create) | SQLite `sessions` table | Full metadata row for the uploaded file |
| Message record (create) | SQLite `messages` table | One row per user turn, one row per assistant turn |
| Session metadata (read) | HTTP response / in-process callers | Returned by `GET /api/sessions/{session_id}` |
| Message history (read) | HTTP response / Data Chat capability | Returned by `GET /api/sessions/{session_id}/messages`; also injected into Gemini prompt as conversation context |

## Operations

### Create Session

Called by the File Upload capability immediately after a DataFrame is successfully parsed.

Writes a new row to the `sessions` table with all metadata fields. Sets `created_at` and `last_active_at` to the current UTC timestamp.

### Get Session

Called by:
- `GET /api/sessions/{session_id}` (client hydrating the sidebar on page load / refresh)
- Data Chat capability (to verify the session exists before running the ReAct loop)

Returns the full session row. Returns `None` (→ 404) if the `session_id` does not exist.

### Append Message

Called by the Data Chat capability twice per Q&A turn: once for the user's question, once for the assistant's answer.

- Inserts a new row into the `messages` table.
- Updates `sessions.last_active_at` to the current UTC timestamp.

The assistant message must only be written after the ReAct loop completes successfully. If the loop aborts (e.g., Gemini returns 503), the assistant message is NOT written — only the user message is written, leaving the turn incomplete. The client will re-enable the input and the user can retry.

> **Assumed:** Partial/incomplete turns (user message written, assistant message missing) are acceptable in v0.1. The chat UI will render such a turn with no assistant reply and allow the user to ask again.

### Get Message History

Called by:
- `GET /api/sessions/{session_id}/messages` (full history for the chat UI)
- Data Chat capability (recent history for Gemini context window)

For the Gemini context window, only the most recent N message pairs are included to stay within token limits.

> **Assumed:** N = 10 message pairs (20 rows) for context injection. This is a reasonable default for v0.1 and can be tuned. The full history is always returned to the UI regardless of this limit.

## External Calls

| System | Call | Failure Handling |
|--------|------|-----------------|
| SQLite | `INSERT INTO sessions` | Raise `DatabaseError`; caller returns 500 |
| SQLite | `SELECT FROM sessions WHERE id = ?` | Raise `DatabaseError`; caller returns 500 |
| SQLite | `INSERT INTO messages` | Raise `DatabaseError`; caller returns 500; message is not written |
| SQLite | `SELECT FROM messages WHERE session_id = ?` | Raise `DatabaseError`; caller returns 500 |
| SQLite | `UPDATE sessions SET last_active_at = ?` | Raise `DatabaseError`; log and continue (non-fatal) |

## Error Cases

| Condition | Behaviour |
|-----------|-----------|
| `session_id` not found | Return `None` to caller; caller raises HTTP 404 |
| SQLite unavailable / file corrupted | Raise `DatabaseError`; caller returns HTTP 500 |
| Duplicate `session_id` on insert | Should never occur (UUID4 collision is astronomically unlikely); if it does, return 500 |

## Data Lifecycle

| Event | SQLite Action |
|-------|--------------|
| File uploaded successfully | `INSERT INTO sessions` with `status = "ready"` |
| File fails to parse | `INSERT INTO sessions` with `status = "error"` and `error_message` |
| User sends a question | `INSERT INTO messages` (`role = "user"`); `UPDATE sessions SET last_active_at` |
| Agent returns an answer | `INSERT INTO messages` (`role = "assistant"`) |
| Server restart | All SQLite records survive; in-memory DataFrame cache is lost (session `status` remains `"ready"` in DB, but the DataFrame must be re-uploaded) |
| Session cleanup | Not implemented in v0.1 — sessions accumulate indefinitely |

## Success Criteria

- [ ] After `POST /api/sessions`, a `Session` row with `status = "ready"` is readable from SQLite.
- [ ] After `POST /api/sessions/{id}/messages`, two `Message` rows are written (user + assistant), and `sessions.last_active_at` is updated.
- [ ] `GET /api/sessions/{id}/messages` returns messages in `created_at` ascending order.
- [ ] After a server restart, `GET /api/sessions/{id}` still returns the session metadata (no 404).
- [ ] After a server restart, `GET /api/sessions/{id}/messages` returns the full prior conversation history.
- [ ] If the ReAct loop fails (agent error), only the user message is written; no assistant message row is created.

## Dependencies

- **Capability 01 (File Upload):** Calls `create_session()` after successful parse.
- **Capability 02 (Data Chat):** Calls `get_message_history()` before the ReAct loop and `append_message()` after.
