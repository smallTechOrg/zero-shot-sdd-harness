# Data Analysis Agent

> All commands run from the repo root (`/Users/sai/Workspace/Code/exp2`).

Upload a CSV. Ask questions in plain English. Gemini answers from the data.

---

## Setup

1. Install Python deps: `uv sync`
2. Install frontend deps: `cd frontend && pnpm install && cd ..`
3. Copy `.env.example` to `.env` and set `AGENT_GEMINI_API_KEY=your_key`
4. Apply DB migrations: `uv run alembic upgrade head`
5. Verify migration: `uv run alembic current` (should show revision 0002)
6. Build frontend: `cd frontend && pnpm build && cd ..`
7. Start server: `uv run python -m src`
8. Open: http://localhost:8001/app/

---

## Running tests

```bash
uv run pytest tests/ -v --tb=short
```

Requires `AGENT_GEMINI_API_KEY` in `.env` for real-provider tests.

Unit-only (no key needed):

```bash
uv run pytest tests/unit/ -v --tb=short
```

---

## API

### `GET /health`

```bash
curl http://localhost:8001/health
```

### `POST /sessions` — upload CSV

```bash
curl -X POST http://localhost:8001/sessions \
  -F "file=@your_data.csv"
```

Response:
```json
{
  "ok": true,
  "data": {
    "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "row_count": 1500,
    "columns": [
      {"name": "product_name", "dtype": "object"},
      {"name": "quantity", "dtype": "int64"},
      {"name": "revenue", "dtype": "float64"}
    ]
  }
}
```

### `POST /sessions/{session_id}/questions` — ask a question

```bash
curl -X POST http://localhost:8001/sessions/3fa85f64-.../questions \
  -H "Content-Type: application/json" \
  -d '{"question": "Which product has the highest revenue?"}'
```

Response:
```json
{
  "ok": true,
  "data": {
    "run_id": "...",
    "answer": "Cherry has the highest revenue at $200.00.",
    "chart_base64": null,
    "chart_type": null,
    "executed_code": null,
    "node_trace": [...],
    "tokens_in": 312,
    "tokens_out": 48,
    "cost_usd": 0.00004,
    "latency_ms": 1240.5
  }
}
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AGENT_GEMINI_API_KEY` | Yes | Google Gemini API key |
| `AGENT_ANTHROPIC_API_KEY` | Optional | Anthropic API key (alternate provider) |
| `AGENT_DATABASE_URL` | Optional | SQLAlchemy URL (default: `sqlite:///./data/agent.db`) |
| `AGENT_LLM_MODEL` | Optional | Override model (default: `gemini-2.0-flash`) |

---

## What works (Phase 1)

- CSV upload (drag and drop or file picker) — column schema preview
- Natural-language Q&A — text answer from Gemini (`gemini-2.5-flash`)
- Observability — tokens in/out, cost, latency, node trace per run
- All answers stored in DB (`analysis_runs` table)

## Coming in Phase 2 (labelled stubs)

- Charts (PNG chart generation from pandas data) — **Phase 2, not yet implemented**
- Code surfacing (show the pandas code used) — **Phase 2, not yet implemented**
