# API

FastAPI, served at `http://localhost:8001`. The frontend builds against this contract in
parallel with the backend. All JSON unless noted. Phase 1 endpoints below.

## `POST /api/datasets`

Upload a CSV and get its profile.

- **Request:** `multipart/form-data` with field `file` (CSV, up to ~100MB).
- **Response 200:**

```json
{
  "id": "uuid",
  "filename": "orders.csv",
  "row_count": 100000,
  "column_count": 12,
  "size_bytes": 8421376,
  "profile": {
    "columns": [
      {"name": "region", "dtype": "string", "missing_count": 0, "distinct_count": 5,
       "top_values": ["West", "East", "North"]},
      {"name": "order_value", "dtype": "float64", "missing_count": 12,
       "min": 1.2, "max": 9980.0, "mean": 142.7}
    ],
    "sample": [{"region": "West", "order_value": 120.5}]
  }
}
```

- **Errors:** `400` (not a CSV / parse error / too large), `500` (profiling failure) with
  `{"detail": "..."}`.

## `POST /api/analyses`

Ask one plain-language question against a dataset; runs the agentic loop.

- **Request:** `{"dataset_id": "uuid", "question": "average order value by region?"}`
- **Response 200:**

```json
{
  "id": "uuid",
  "dataset_id": "uuid",
  "question": "average order value by region?",
  "status": "completed",
  "answer": "Average order value is highest in the West ($168) ...",
  "result": {"West": 168.2, "East": 131.0},
  "chart_spec": { "mark": "bar", "encoding": { "...": "..." } },
  "code": "df.groupby('region')['order_value'].mean().to_dict()",
  "steps_taken": 2,
  "created_at": "2026-06-28T12:00:00Z"
}
```

- **Failure (cap hit / fatal):** `status: "failed"`, `error_message` set, `code` shows the last
  attempt — HTTP 200 (the run is a recorded outcome, not a transport error).
- **Errors:** `404` (unknown `dataset_id`), `400` (empty question), `500` (unexpected).

## `GET /api/analyses?dataset_id=<uuid>`

Run-history audit for a dataset (most recent first).

- **Response 200:** `[{id, question, status, answer, code, steps_taken, created_at}, ...]`

## `GET /api/analyses/{id}`

Full single run record (question, code, result, chart_spec, answer, status, timestamps).

## `GET /health`

Liveness — `{"status": "ok"}` (skeleton-provided).

## Notes

- The privacy boundary is server-side: no endpoint ever returns raw rows to the LLM; the UI
  receives only profile/sample/aggregates + computed results.
- Deferred endpoints (sessions, library, annotations, cost, sources) are NOT part of Phase 1
  and are added in their respective phases — see [roadmap.md](roadmap.md).
