# API

---

## API Style

REST + Server-Sent Events (SSE) for live step status, served by FastAPI on the single origin (`:8001`). The static UI is served at `/app/`. The skeleton's `/runs` endpoints may remain but are superseded by the dataset endpoints below.

## Endpoints / Commands

### `POST /datasets`  *(Phase 1)*
**Purpose:** upload + locally profile a CSV ([profile_dataset](./capabilities/profile_dataset.md)).

**Request:** `multipart/form-data` with `file`.

**Response:**
```json
{ "data": { "dataset_id": "uuid", "name": "sales.csv",
  "row_count": 10432, "column_count": 7,
  "profile": [{"name":"region","dtype":"string","distinct_count":4,"null_count":0,"sample_values":["NW","SE"]}],
  "sample_rows": [{ "region": "NW", "amount": 120.5 }] } }
```

**Error cases:** 400 unparseable/too-large file; 500 storage failure.

### `POST /datasets/{id}/ask`  *(Phase 1)*
**Purpose:** ask a question; runs the graph; streams steps, then returns the answer ([answer_question](./capabilities/answer_question.md), [visualize_result](./capabilities/visualize_result.md)).

**Request:**
```json
{ "question": "how many sales per region?", "conversation_id": "uuid-or-null" }
```

**Response (final event / JSON):**
```json
{ "data": { "turn_id": "uuid", "conversation_id": "uuid",
  "answer": "NW had 4,210 sales; SE 3,118; ...",
  "plan": ["group by region", "count rows"],
  "code": "df.groupby('region').size().reset_index(name='count')",
  "result_table": [{"region":"NW","count":4210}],
  "chart_spec": {"chart_type":"bar","x":"region","y":"count","title":"Sales per region"},
  "follow_ups": ["Which region grew fastest?", "Show monthly trend for NW"],
  "token_usage": {"prompt": 812, "completion": 96, "total": 908},
  "estimated_cost_usd": 0.0004,
  "assumptions": [] } }
```
**SSE stream (during run):** `{"step":"plan","status":"running"}` … `{"step":"execute_local","status":"done"}`.

**Error cases:** 404 unknown dataset; 422 missing question; 500 graph failure (still persists a failed Turn).

### `GET /datasets`  *(Phase 2)*
Lists library datasets with summaries + `daily_cost_total`.

### `GET /conversations/{id}`  *(Phase 2)*
Returns the conversation's ordered Turn audit records.

### `POST /datasets/join` and `POST /datasets/{id}/save-derived`  *(later phase)*
Multi-file join (incl. Excel multi-sheet) and derived-dataset saving.

## Authentication

None — single-user, local-only process bound to localhost. No auth at MVP.
