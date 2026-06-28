# API — Pandora

FastAPI on `:8001`. JSON envelope is the skeleton's `ok(data)` / `api_error(code, message, status)`. The static frontend is served at `/app/`; the frontend calls these routes same-origin. Routers: `src/api/datasets.py`, `src/api/questions.py`.

## Conventions
- Success: `{ "data": <payload>, "error": null }`.
- Error: HTTP 4xx/5xx with `{ "detail": { "code": "...", "message": "..." } }`.
- One streaming endpoint (`/ask`) uses SSE (`text/event-stream`); all others are plain JSON.

## Phase 1 Endpoints

### `POST /datasets` — upload + profile
Multipart `file` (`.csv`/`.xlsx`). Stores, converts to Parquet, profiles (full data), asks Gemini for suggestions.
- **200** → `data: { dataset_id, filename, row_count, column_count, profile, suggested_questions, status }`
- **422** → parse failure (`code: "PARSE_ERROR"`), nothing persisted.
- **413** → file over the size limit.

### `GET /datasets/{id}` — fetch profile
- **200** → `data: { ...dataset fields..., profile, suggested_questions }`
- **404** → unknown id.

### `POST /datasets/{id}/ask` — ask a question (SSE stream)
Body `{ "question": string }`. Returns `text/event-stream`. Event sequence:
```
event: step   data: {"step":"generating_code","index":0,"elapsed_ms":..}
event: step   data: {"step":"running_code","index":1,"elapsed_ms":..}
event: step   data: {"step":"retrying","index":2,"elapsed_ms":..}        # only if a retry occurs
event: step   data: {"step":"summarising","index":..,"elapsed_ms":..}
event: answer data: {"question_id","answer_text","chart_spec","summary_table",
                     "code","usage":{"prompt_tokens","completion_tokens","cost_usd"},
                     "daily_total_usd","status":"completed"}
# OR, on failure:
event: error  data: {"question_id","message","code_attempted","status":"stuck"}
```
The `questions` row is persisted before the final event regardless of outcome.

### `GET /questions/{id}` — fetch a past question
- **200** → `data: { id, dataset_id, question, code, answer_text, chart_spec, summary_table, usage, status, created_at }`
- **404** → unknown id.

### `GET /cost/today` — running daily total
- **200** → `data: { date, total_usd, question_count }`

### `GET /healthz` — skeleton health route (kept)

## Phase 2+ Endpoints (stubbed/disabled in Phase 1 UI)
- `GET /datasets/{id}/questions` — paginated history list (Phase 2).
- `GET /datasets` — dataset library across sessions (Phase 3).
- Follow-up uses the same `POST /datasets/{id}/ask` with an added `conversation_id` (Phase 2).
- Deep analysis uses the same `/ask` with `deep_mode: true` (Phase 4).

## Notes
- Streaming applies **only** to `/ask`. The frontend reads the SSE stream to render live steps + the final answer.
- No raw rows appear in any response beyond the computed summary table (≤ 200 rows of *result*, not source data) — and never in any payload sent **to** the LLM (see [architecture.md](architecture.md#privacy-boundary)).
