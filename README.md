# DataChat

Upload a CSV or JSON dataset and ask plain-English questions about your data. A Google Gemini ReAct agent generates pandas operations, executes them against your actual data, and returns a grounded answer with a full reasoning trace.

> **All commands run from the repo root.**

---

## Quick Start

### 1. Install dependencies

```bash
# From: repo root
uv sync
```

### 2. Configure environment

```bash
# From: repo root
cp .env.example .env
# Edit .env and set DATACHAT_GEMINI_API_KEY=your-key-here
```

### 3. Apply database migrations

```bash
# From: repo root
uv run alembic upgrade head
uv run alembic current    # must show a revision hash — blank = migration not applied
```

### 4. Run the server

```bash
# From: repo root
uv run python -m datachat
```

Server starts at **http://localhost:8001**

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATACHAT_DATABASE_URL` | No | `sqlite:///./datachat.db` | SQLite DB path |
| `DATACHAT_GEMINI_API_KEY` | Yes (live mode) | `` | Your Google Gemini API key |
| `DATACHAT_LLM_MODEL` | No | `gemini-2.5-flash` | Gemini model name |
| `DATACHAT_MAX_ITERATIONS` | No | `10` | Max ReAct loop iterations per question |
| `DATACHAT_MAX_UPLOAD_BYTES` | No | `52428800` | Max file size (50 MB) |
| `DATACHAT_LOG_LEVEL` | No | `INFO` | Log level |
| `PORT` | No | `8001` | HTTP port |

**Stub mode:** If `DATACHAT_GEMINI_API_KEY` is not set or empty, the app runs in stub mode — all LLM calls return deterministic placeholder responses and a visible banner is shown in the UI. Set the API key to switch to live Gemini automatically; no other flag needed.

---

## Running Tests

```bash
# From: repo root
uv run pytest
```

Tests run in stub mode — no API key required. All 14 tests should pass.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Server status + LLM provider |
| POST | `/api/sessions` | Upload CSV/JSON file |
| GET | `/api/sessions/{id}` | Session metadata |
| POST | `/api/sessions/{id}/messages` | Ask a question |
| GET | `/api/sessions/{id}/messages` | Message history |

Full OpenAPI docs: **http://localhost:8001/docs**

---

## How It Works

1. Upload a CSV/JSON file → parsed into a pandas DataFrame held in memory for your session
2. Ask a question in plain English → Gemini generates a one-line pandas expression
3. Expression is validated against a frozenset allowlist (no `eval`) and executed against your real data
4. Result is fed back to Gemini; it loops (up to 10 iterations) until it can give a `FINAL ANSWER`
5. Answer + full reasoning trace returned to the browser

---

## Deferred (Future Phases)

- Chart/visualization output (Phase 3)
- Cross-file joins (Phase 4)
- Query history UI (Phase 5)
- Streaming token output (Phase 6)
