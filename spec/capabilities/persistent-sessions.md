# Capability: Persistent Sessions

## What It Does

Creates named analytical sessions, stores conversation history and dataset references in SQLite, and restores the full session state (datasets + messages) when the user returns — even after a page refresh or server restart.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| `POST /sessions` request | empty JSON body | Browser (user click "New Session") | Yes (to create) |
| `session_id` in `localStorage` | string (UUID) | Browser `localStorage` key `analyst_session_id` | Yes (to restore) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `Session` record | SQLite row | `sessions` table |
| `SessionModel` | Pydantic model | `POST /sessions` JSON response (201) |
| Session list | list of `SessionModel` | `GET /sessions` JSON response |
| Full session state | `SessionModel` + datasets + messages | `GET /sessions/{id}` JSON response |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | INSERT session; SELECT sessions; SELECT session+datasets+messages | Return appropriate HTTP error; surface in UI |

## Business Rules

- A new session is auto-named "Session {n}" where n is the count of existing sessions + 1.
- The `session_id` is a server-generated UUID; the browser stores it in `localStorage` after creation.
- On page load, the browser reads `localStorage.analyst_session_id` and calls `GET /sessions/{id}` to restore state. If 404 (session deleted in Phase 2 or DB wiped), the browser clears `localStorage` and shows the empty state.
- Sessions are listed newest-first in `GET /sessions`.
- `GET /sessions/{id}` returns the session's full state: session metadata + all datasets + all messages (ordered by `created_at` ascending). The messages list includes both user and assistant messages with their content.
- Session names default to "Session {n}" and cannot be changed in Phase 1 (rename is Phase 2).
- Sessions are not deleted in Phase 1 (delete is Phase 2). They accumulate indefinitely.
- `dataset_count` and `message_count` in the session list are computed as SQL COUNT at query time (not cached fields).

## Success Criteria

- [ ] `POST /sessions` returns 201 with a valid UUID `session_id` and a name like "Session 1".
- [ ] After upload and a chat turn, refreshing the browser fully restores: the session in the sidebar is selected, datasets appear in the dataset panel, and the chat history shows the prior messages.
- [ ] After a server restart (SQLite file persists), reopening the app restores the prior session via `localStorage` + `GET /sessions/{id}`.
- [ ] `GET /sessions` returns all sessions with correct `dataset_count` and `message_count`.
- [ ] `GET /sessions/{id}` for a non-existent ID returns 404.
- [ ] Creating 3 sessions produces "Session 1", "Session 2", "Session 3" names in order.
