# API

---

## API Style

REST over HTTP, served single-origin by FastAPI on port 8001. The built Next.js app is mounted at `/app`; API routes are at the root. **Success envelope:** `{"data": ..., "error": null}` via `ok(data)`. **Error envelope:** HTTP 4xx/5xx with `{"detail": {"code": ..., "message": ...}}` via `api_error(code, message, status_code)`. No authentication (single local user).

> Routers live in `src/api/` — one module per resource, registered in `create_app()`. The boilerplate `/runs` POST/GET stays unless it conflicts; the canonical analysis route is `/ask`. `GET /runs/current` is ADDED to `runs.py`.

## Endpoints / Commands

### `GET /health`
Returns `ok({status:"ok", provider:"<gemini|openrouter|stub|anthropic>"})`. The `provider` field drives the UI stub banner. Always 200.

### `GET /` and `/app`
The single-origin Next.js UI (static mount). Server starts API-only if `frontend/out/` is absent.

### `POST /upload`
Multipart `file`; form `context?`, `notes_file?`; query `force=false`. Parses (pandas), computes sha256, duplicate-checks (C10), saves CSV + Parquet, creates a `datasets` row, triggers async C30 notes. Accepts `.csv/.tsv/.txt/.json/.xlsx/.xls`. Returns `{dataset_id, filename, format, row_count, col_count, columns, context, auto_notes_status}`.

| Status | Condition |
|--------|-----------|
| 409 | `duplicate_dataset` (with `match_type` + `existing_*`); resolvable with `force=true` |
| 400 | bad extension / unparseable / empty file |
| 500 | disk write failure |

### `GET /datasets`
List datasets incl. `origin`, `stale`, `derived_*`, `derivation_description`. Always 200.

### `GET /datasets/{id}`
Full metadata incl. `columns_schema[{name, dtype-alias}]` (alias table in `spec/data.md`), `context`, `derivation_code`, `auto_notes_status`. **404** if missing.

### `GET /datasets/{id}/preview?rows=10`
`{columns, rows}` first N rows (clamp 1..50); per-cell formatting (floats round 4, whole floats → int, NaN → null). **404** missing / **500** read error.

### `GET /datasets/{id}/sessions`
Sessions scoped to that dataset. **404** missing.

### `DELETE /datasets/{id}`
Cascade delete (+ recursive derived, C15). **404** missing / **409** `dataset_in_use`.

### `DELETE /datasets`
Delete all + cascade.

### `PATCH /datasets/{id}/context`
Body `{context}` (≤4000). **400** `context_too_long` / **404** missing.

### `POST /datasets/{id}/describe`
C30 trigger: set `auto_notes_status=pending`, generate notes async. **404** missing.

### `POST /datasets/{id}/re-derive`
C25 re-run `derivation_code` vs current parents; clears `stale`. **400** `not_derived` / **404** `parent_not_found` / **400** `re_derive_error`.

### `POST /datasets/{id}/clean`
C24 NL cleaning PREVIEW: LLM generates pandas code, run on a copy, return `{code, before/after row+col counts, previews}`. **422** on clean exec error. **404** missing.

### `POST /datasets/{id}/clean/apply`
C24 apply code in place; rewrite CSV + Parquet, update counts. **422** exec error / **404** missing.

### `POST /ask`
Body `{dataset_id? | dataset_ids?, question, session_id?, skip_clarification:false}`.
Pre-flight C26 (unless `skip_clarification`) → may return `{type:"clarification", clarification_question, run_id, session_id}` (thin run, status `clarification`). Else resolve datasets (explicit or C19 selector), create the run (`status=running`), run the agent, return:
```json
{"type":"answer","run_id":"...","session_id":"...","dataset_ids":[...],
 "derived_dataset_ids":[...],"datasets_used":[...],"selector_reasoning":"...",
 "answer_markdown":"...","answer_html":"...","iteration_count":3,
 "tokens_input":1234,"tokens_output":567,"status":"completed",
 "is_best_effort":false,"steps":[...],"suggested_questions":[...],
 "prompt_breakdown":{...}}
```

| Status | Condition |
|--------|-----------|
| 404 | dataset or session not found |
| 400 | empty question / session mismatch / >20 turns / no datasets uploaded |

### `GET /sessions`
All sessions, most-recently-updated first; each with `turn_count`, `first_question`. Always 200.

### `GET /sessions/{id}`
Session + `turns[]` (each turn carries `prompt_breakdown`). **404** missing.

### `PATCH /sessions/{id}/name`
Rename. **404** missing.

### `DELETE /sessions/{id}` and `DELETE /sessions`
Delete one / all sessions.

### `GET /runs/current`
Most recent run `{run_id, status, iteration_count, max_iterations}` (status `idle` when none). Used for live progress polling (~1/s). Always 200.

### `GET /stats/daily`
`{date, model, tokens_input, tokens_output, query_count, context_limit}` aggregated over today's completed runs (server-local day); `context_limit` from a hard-coded model table (unknown → 128000). Always 200.

### `GET /memory` and `PATCH /memory`
Read / replace the global persistent memory text; PATCH triggers C31 compression. Memory is injected into every `plan_action` prompt as authoritative. Always 200 on read; PATCH **400** if body invalid.

## Authentication

None — single local user. No API keys, sessions, or tokens for callers. Provider keys live in `.env` and never leave the server.
