# IR Box Culvert Design & Proof-Check Agent

> **All commands run from the repo root.** The repo root IS the project — there is no subdirectory to `cd` into (the only exception is the explicit `cd frontend` step in the frontend build).

An agentic AI demonstrator for Indian Railways civil engineering: it designs single-cell RCC box culverts from natural-language requests and proof-checks its own design. From one prompt it streams a visible plan, extracts typed parameters with Gemini, runs a deterministic IRS engineering core (no LLM in the maths), and produces a dimensioned GA drawing as genuine DXF plus in-browser SVG — with a clause-cited calc sheet, automatic proof-check memo, and 3D model landing in later phases. Everything runs on your laptop; the only network call is the Gemini API.

## Setup

```bash
cp .env.example .env
```

Edit `.env` and set `AGENT_GEMINI_API_KEY` to your Google AI Studio API key (this is the only required manual step; the key never leaves `.env`).

## Install & build the frontend

```bash
cd frontend && pnpm install && pnpm build && cd ..
```

This produces `frontend/out/`, which the backend serves at `/app`. The server also starts without it (API-only mode).

## Database

```bash
uv run alembic upgrade head
uv run alembic current      # must print a revision (e.g. "0002 (head)") — blank output means it failed
```

## Run

```bash
uv run python -m src
```

Then open <http://localhost:8001/app/>.

| URL | What |
|-----|------|
| `http://localhost:8001/app/` | The Design Studio UI |
| `http://localhost:8001/health` | API liveness check |
| `http://localhost:8001/docs` | Interactive API docs (Swagger) |

Try the canonical prompt:

```
single box culvert, 4 m clear span, 3 m height, 2.5 m cushion, BG single line, 25t loading
```

Watch the six-step tracker, then open the Drawing tab: pan/zoom the GA sheet and click **Download DXF** (opens in AutoCAD and free viewers). A follow-up like `increase the fill to 4 m` regenerates the drawing in the same session.

## Test

```bash
uv run pytest tests/unit -q                # no API key needed
uv run pytest tests/integration -q         # runs the real Gemini pipeline — needs AGENT_GEMINI_API_KEY in .env
npx playwright test tests/e2e              # E2E — boots the server itself via `uv run python -m src`
```

## Phase status

| Feature | Status |
|---------|--------|
| NL prompt → parameter extraction (Gemini), incl. one-clarifying-question + scope gate | **Real (Phase 1)** |
| Deterministic IRS sizing engine (member sizing, geometry, assumptions trail) | **Real (Phase 1)** |
| GA drawing — genuine DXF + pan/zoom SVG in the browser | **Real (Phase 1)** |
| Session turn memory + refinement regeneration | **Real (Phase 1)** |
| Live step tracker, narration, tokens/cost display (SSE) | **Real (Phase 1)** |
| Calc Sheet tab (clause-cited sheet, drill-down trail) | Labelled stub — coming in Phase 2 |
| Proof-Check tab (12-item checklist, FE cross-check, verdict memo) | Labelled stub — coming in Phase 2 |
| 3D Model tab (GLB viewer + STEP download) | Labelled stub — coming in Phase 3 |
| Library tab (all past runs, presets editing) + suggestion chips | Labelled stub — coming in Phase 3 |

## Environment variables

All are read from `.env` (prefix `AGENT_`). Only the Gemini key is required.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `AGENT_GEMINI_API_KEY` | **yes** | — | Google AI Studio key; used for all agent LLM steps |
| `AGENT_DATABASE_URL` | no | `sqlite:///./data/agent.db` | SQLite audit-trail DB (SQLite IS production for this local demo) |
| `AGENT_ARTIFACTS_DIR` | no | `data/artifacts` | Root for generated artefact files (`<run_id>/ga.dxf`, `ga.svg`, ...) |
| `AGENT_LLM_PROVIDER` | no | auto-detected | `gemini` for this project |
| `AGENT_LLM_MODEL` | no | `gemini-2.5-pro` | Model for all agent nodes |
| `AGENT_GEMINI_INPUT_COST_PER_MTOK` | no | `1.25` | USD per million prompt tokens (cost display) |
| `AGENT_GEMINI_OUTPUT_COST_PER_MTOK` | no | `10.0` | USD per million completion tokens (cost display) |
| `AGENT_LOG_LEVEL` | no | `INFO` | structlog JSON log level |

## Project layout

```
src/            FastAPI API (api/), LangGraph agent (graph/), Gemini client (llm/),
                deterministic IRS core (engine/, drawing/), SQLite audit trail (db/),
                settings (config/), typed domain models (domain/), observability/
frontend/       Next.js static export (served at /app)
alembic/        DB migrations (0002 = culvert schema + seeded default preset)
tests/          unit/ (no key), integration/ (real Gemini), e2e/ (Playwright)
spec/           The spec that drives the build (roadmap, architecture, api, data, ui, agent)
data/           SQLite DB + artefact files (gitignored, created on first run)
```
