# Capability: Session Management

## What It Does

Creates and tracks isolated analysis sessions identified by an unguessable UUID so that each user's uploaded files and conversation history are kept separate and automatically scoped to that session's lifetime.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| (none for session creation) | — | POST /sessions | No |
| session_id | UUID string | URL path parameter (all subsequent requests) | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| session_id | UUID v4 string | API response body + stored in `sessions` table |
| Session record | object with `id`, `created_at` | `sessions` table in SQLite |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite (session DB) | INSERT session record on creation; SELECT session on every request to validate it exists | Return HTTP 404 if session not found; HTTP 500 on DB error |
| Local filesystem | Create per-session temp directory at session creation | Return HTTP 500; roll back session DB record |

## Business Rules

- Session IDs are UUID v4 generated server-side — never user-supplied
- Each session gets an isolated temp directory: `/tmp/sessions/{session_id}/`
- Session data (DB records + temp files) is NOT persisted between server restarts — SQLite is in-memory or wiped on startup, and the temp directory is cleared
- All API endpoints for files and messages validate that the `session_id` exists; unknown session IDs return HTTP 404
- No authentication or login is required; possession of a valid session UUID is the only credential
- Sessions are not shared between users and have no expiry enforced in Phase 1 (process lifetime only)

## Success Criteria

- [ ] POST /sessions → returns a UUID v4 `session_id` in < 200 ms
- [ ] Two consecutive POST /sessions calls → return two different UUIDs
- [ ] Using a non-existent session_id on any /sessions/{session_id}/* endpoint → returns HTTP 404
- [ ] After server restart, previously created session IDs are no longer valid (return HTTP 404)
- [ ] Session temp directory exists on disk after POST /sessions succeeds
