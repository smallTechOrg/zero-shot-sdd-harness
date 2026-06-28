# Roadmap

---

## What This Agent Does

A personal, local-first data-analysis agent. The user uploads tabular files (CSV; Excel later) and has a back-and-forth conversation to get direct answers with key numbers, automatically-chosen interactive charts, and summary tables. Critically, it is privacy-preserving and transparent: the LLM (Gemini) only ever sees a dataset's schema/profile and a tiny sample — the agent generates analysis code that runs LOCALLY against the real files, so raw rows never leave the machine. Every answer shows the exact code it ran, the plan it followed, and its token/cost, and the full run history is persisted as an audit trail.

## Who Uses It

A single technical power user who runs data questions many times a day and acts on the answers (production-grade), values complete code transparency, and has a hard privacy requirement that raw data not leave their machine.

## Core Problem Being Solved

Replaces the slow loop of hand-writing pandas/SQL for every ad-hoc question, and replaces privacy-unsafe "paste your data into a chatbot" tools — by generating and running analysis code locally while keeping raw data on-machine, with a full audit trail.

## Success Criteria

- [ ] Upload a CSV → get a correct auto-profile (every column typed, true row count).
- [ ] Ask an NL question → get a correct direct answer computed locally over ALL rows, with the exact code shown.
- [ ] An appropriate chart (auto-chosen) and/or summary table renders interactively per answer.
- [ ] A follow-up question resolves against prior conversation context.
- [ ] Tests assert the LLM payload contains profile + sample only — never raw rows (privacy boundary airtight).

## What This Agent Does NOT Do (Out of Scope)

- No cloud/multi-tenant; single local user only.
- No sending raw rows to any LLM, ever.
- No auth, no sharing, no scheduled/automated reports.
- No ML model training; ad-hoc analytical answers only.
- v1 input is CSV; Excel/multi-sheet and multi-file joins are later phases.

## Key Constraints

- **Privacy boundary (defining):** LLM sees schema + small sample only; generated code executes locally; raw rows never leave the machine.
- Files up to ~100MB; answers under ~30s.
- Provider is Gemini (`AGENT_GEMINI_API_KEY` in `.env`); default model `gemini-2.5-flash`.
- Single FastAPI process on port 8001 serving API + UI at `/app/`; SQLite local DB.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Backend minimal but REAL on the one core path; frontend visually complete with clearly-labelled NON-FUNCTIONAL stubs for everything later.

### Phase 1 — Upload → Ask → Answer (with code + chart)

- **Goal:** Upload one CSV → agent auto-profiles it → user asks an NL question → agent plans, generates and RUNS analysis code locally → returns a direct answer WITH the exact code shown and an appropriate chart/table. Conversation history carries across turns in the session.
- **Independent slices (parallel build units):**
  - `db-migration` (backend) — Alembic migration for [Dataset](./data.md#entity-dataset), [Conversation](./data.md#entity-conversation), [Turn](./data.md#entity-turn) + SQLAlchemy models. Deps: none.
  - `executor-and-graph` (backend) — privacy-safe context builder, local pandas/DuckDB executor, and the LangGraph nodes (load_context → plan → generate_code → execute_local → visualize → finalize/handle_error) extended in place over the skeleton graph; new prompts in `src/prompts/`. Deps: none (defines its own state; integrates with models at runtime).
  - `api-routes` (backend) — `POST /datasets` (upload+profile) and `POST /datasets/{id}/ask` (SSE step stream + final JSON); wires runner→graph→DB. Deps: declared on `db-migration` (models) and `executor-and-graph` (graph) — serialize after those two; build the route signatures against the data/agent spec in parallel, integrate last.
  - `frontend` (frontend) — Workspace page: upload zone + auto-profile view, chat thread, answer card (answer, live step status, collapsible code/plan, Recharts chart, table, follow-up chips, per-turn cost), plus clearly-labelled "Coming soon" stubs (library sidebar, daily-cost-history, compare/save/Excel buttons). Deps: none (codes to the [api.md](./api.md) contract).
- **Key surfaces / files:**
  - `db-migration`: `src/db/models.py`, `alembic/versions/*`
  - `executor-and-graph`: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/agent.py`, `src/graph/edges.py`, `src/analysis/profiler.py`, `src/analysis/executor.py`, `src/llm/context.py`, `src/prompts/plan.md`, `src/prompts/generate_code.md`, `src/prompts/visualize.md`
  - `api-routes`: `src/api/datasets.py`, `src/graph/runner.py`, `src/domain/*`
  - `frontend`: `frontend/src/app/page.tsx`, `frontend/src/components/*`
- **Gate command:** `uv run alembic upgrade head` then `uv run pytest` (real Gemini via `.env`; SQLite is the production DB) then `uv run python -m src` boots clean and `cd frontend && pnpm build` produces a styled `/app/`. The phase-1 test MUST assert: (a) profile row_count equals true file row_count over a fixture of **≥5,000 rows** (so a sampled count ≠ full count — proves local full-data execution), (b) a follow-up turn uses prior context, and (c) the captured LLM payload contains profile+sample only, never the full row set.
- **How the user tests it (handoff seed):** run `uv run python -m src`, open `http://localhost:8001/app/`. Upload a CSV (≥a few thousand rows). See the auto-profile. Ask "how many rows per <category column>?" → see a direct answer, expand "Show code" to read the pandas it ran, see the bar chart and table, and the per-turn cost. Ask a follow-up "now only for <value>" → confirm it uses context. Labelled "Coming soon" stubs: library sidebar, daily-cost history, compare/save/Excel buttons — these are intentional placeholders, not bugs.

### Phase 2 — Dataset Library, Persistence & Cost Dashboard

- **Goal:** wire the labelled stubs into real features: datasets and full audit trail persist across sessions/days; the library sidebar lists datasets and opens past conversations; the daily running cost total is real ([dataset_library](./capabilities/dataset_library.md)).
- **Independent slices (parallel build units):**
  - `library-api` (backend) — `GET /datasets`, `GET /conversations/{id}`, daily cost aggregation. Deps: none (Phase-1 tables already exist).
  - `frontend-library` (frontend) — make the sidebar real (list datasets, click to load, browse audit trail), real header daily-cost total. Deps: declared on `library-api` contract (codes to it; integrate last).
- **Key surfaces / files:** `library-api`: `src/api/datasets.py` (new read routes), `src/api/conversations.py`; `frontend-library`: `frontend/src/components/Library*.tsx`, header component.
- **Gate command:** `uv run pytest` (real Gemini + SQLite) — a test uploads a dataset, runs a turn, **restarts the session/engine**, and asserts the dataset + its turn audit are still listed and the daily cost total equals the summed per-turn costs.
- **How the user tests it (handoff seed):** run the app, upload a dataset, ask something, stop and restart `uv run python -m src`, reopen `/app/` → the dataset appears in the (now real) sidebar; clicking it shows the prior conversation with code/result/cost; the header shows the real daily cost total. Stubs remaining: compare/save/Excel buttons.

### Phase 3 — Multi-File Joins, Excel Multi-Sheet & Derived Datasets

- **Goal:** turn the last labelled stubs real — join/compare multiple datasets and Excel workbooks with multiple sheets; save cleaned/derived datasets back into the library ([dataset_library](./capabilities/dataset_library.md), extends [profile_dataset](./capabilities/profile_dataset.md)).
- **Independent slices (parallel build units):**
  - `excel-and-join` (backend) — Excel/multi-sheet profiling (openpyxl), `POST /datasets/join`, `POST /datasets/{id}/save-derived`; join profile built without sending joined raw rows to the LLM. Deps: none.
  - `frontend-multi` (frontend) — enable compare/save/Excel UI; multi-dataset selection. Deps: declared on `excel-and-join` contract.
- **Key surfaces / files:** `excel-and-join`: `src/analysis/profiler.py` (excel), `src/analysis/join.py`, `src/api/datasets.py` (join/save routes); `frontend-multi`: `frontend/src/components/*`.
- **Gate command:** `uv run pytest` (real Gemini + SQLite) — a test uploads a multi-sheet Excel + a second CSV, performs a join over a **≥5,000-row** combined set, asserts the result is computed locally over all rows, asserts the LLM payload carries only joined profile/sample, and asserts a saved derived dataset reappears in the library.
- **How the user tests it (handoff seed):** upload an Excel workbook (multiple sheets) and a CSV, use "Compare datasets" to join them, ask a cross-dataset question, then "Save cleaned dataset" → it appears in the library as a new dataset. No remaining stubs.
