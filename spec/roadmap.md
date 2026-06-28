# Roadmap

## What This Agent Does

A single-user, browser-based **privacy-preserving data analysis agent**. The user uploads CSV/Excel files into a persistent library, then converses with their data in natural language. The agent plans an approach, generates pandas analysis code, executes that code **locally** against the real data, and returns plain-language answers with key numbers, charts, and summary tables. The defining property: **raw data rows never leave the machine** — the LLM (Gemini) sees only schema, column profiles, aggregates, and summaries, and writes code that runs against the real rows in a local sandbox. Every query, the code it ran, and the result are persisted as a full audit trail.

## Who Uses It

A single technical-but-not-expert individual (analyst, researcher, founder, ops person) working with sensitive or proprietary tabular data on their own machine. They want the leverage of an LLM data analyst without ever transmitting their actual records to a third party.

## Core Problem Being Solved

LLM data tools normally require uploading raw data to the model. For sensitive data that is a non-starter. This agent gives the conversational-analyst experience while guaranteeing — architecturally, not by policy — that raw rows stay local. It replaces the manual loop of "write pandas, run it, read the numbers, write the next bit of pandas."

## Success Criteria

- [ ] A user uploads a CSV (up to ~100MB), asks a natural-language question, and receives a correct plain-language answer with key numbers, streamed live.
- [ ] The exact pandas code the agent generated and ran is visible in the UI for every answer.
- [ ] No raw data row is ever included in any payload sent to the LLM — verifiable from the persisted audit trail (only schema/summaries appear in LLM-bound payloads).
- [ ] Conversation context carries across turns: a follow-up like "now break that down by region" works without restating the dataset.
- [ ] Every query, generated code, and result is persisted to SQLite and survives a restart.

## What This Agent Does NOT Do (Out of Scope)

- No multi-user / auth / sharing — strictly single-user, single-machine.
- No cloud database, no remote execution — SQLite + local sandbox only.
- No sending raw rows to the LLM under any circumstance (the hard constraint).
- No automated data cleaning / ETL pipelines, no scheduled jobs.
- No write-back to the source files (analysis is read-only over uploaded data).
- No ML model training; analysis = pandas-level aggregation/statistics/charts.

## Key Constraints

- **Privacy (hard):** only schema, column profiles, aggregates, summaries leave to the LLM. Raw rows stay local. See [architecture.md](architecture.md#privacy-boundary).
- **File size:** CSVs up to ~100MB; read with dtype inference, profile without loading full copies where avoidable.
- **Sandbox:** generated pandas runs in a restricted local subprocess (no network, no filesystem writes outside a temp dir, time + memory limits).
- **LLM:** Gemini via `AGENT_GEMINI_API_KEY`. Stream tokens for the answer.
- **DB:** SQLite is the production database for this single-user tool (see Stack assumption). It is the gate DB — not a substitute for Postgres.
- **Single-origin serve:** app served at `http://localhost:8001/app/`; run via `uv run python -m src`.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win — the privacy proof.**

### Phase 1 — Privacy-preserving single-question loop

- **Goal:** Upload a CSV → auto-profile it → ask ONE natural-language question → agent plans, generates pandas, runs it LOCALLY (rows never sent to the LLM), returns a STREAMED plain-language answer AND shows the exact code it ran. The full LangGraph graph is real on this path; Gemini is the real provider; the run (query + code + result + LLM payloads) is persisted and structured-logged.
- **Independent slices (parallel build units):**
  - `db-schema` (backend) — SQLAlchemy models + Alembic migration for `datasets`, `dataset_profiles`, `sessions`, `queries`; extend `init_db`. Deps: none.
  - `ingest-profile` (backend) — file upload handler, local file storage, CSV load + auto-profiler (columns, dtypes, ranges, missing counts, sample-free summaries). Deps: none (writes its own module; consumes `db-schema` models at integration — declared dep on `db-schema`).
  - `sandbox-exec` (backend) — restricted local subprocess that runs generated pandas against a dataset file and returns a captured result/scalar/table. Deps: none.
  - `agent-graph` (backend) — replace `transform_text` node with the analysis graph: `plan → generate_code → execute_locally → summarize`; state, edges, error-handler, finalize; privacy boundary enforced (only profile/summary → LLM). Streaming runner + SSE. Deps: `sandbox-exec`, `ingest-profile`, `db-schema`.
  - `api-routes` (backend) — `POST /datasets` (upload), `GET /datasets/{id}/profile`, `POST /sessions/{id}/query` (SSE stream). Deps: `agent-graph`, `ingest-profile`.
  - `frontend` (frontend) — real UI for upload + profile display + ask + streamed answer + shown code; clearly-labelled NON-FUNCTIONAL stubs for deferred features (charts, tables, library/compare, Excel, cost meter, follow-ups, audit UI, clarify/plan gates). Deps: none (codes against the documented API contract in [api.md](api.md)).
- **Key surfaces / files:**
  - `db-schema`: `src/db/models.py`, `alembic/versions/*`.
  - `ingest-profile`: `src/data/ingest.py`, `src/data/profile.py`, `src/data/storage.py`.
  - `sandbox-exec`: `src/execution/sandbox.py`, `src/execution/runner_proc.py`.
  - `agent-graph`: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/analysis/planner.py`, `src/analysis/codegen.py`, `src/prompts/plan.md`, `src/prompts/codegen.md`, `src/prompts/answer.md`.
  - `api-routes`: `src/api/datasets.py`, `src/api/query.py`, `src/api/__init__.py`, `src/domain/*`.
  - `frontend`: `frontend/src/app/page.tsx`, `frontend/src/components/*`, `frontend/tests/e2e/*`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest` then `cd frontend && pnpm build` (static export styled render) and `cd frontend && pnpm exec playwright test` (E2E against the running app at `http://localhost:8001/app/`).
- **How the user tests it (handoff seed):** Run `cd frontend && pnpm build` then `uv run python -m src`. Open `http://localhost:8001/app/`. Upload a CSV (e.g. a sales export). See the auto-profile (columns, types, missing %). Type a question ("What's the total revenue by month?"). Watch live step updates ("Planning…", "Running analysis…") and the streamed answer with numbers. Click "Show code" to see the exact pandas that ran. **Real:** upload, profile, ask, streamed answer, shown code. **Labelled stubs (greyed, marked "Coming soon"):** charts, summary tables, file library/compare, Excel sheets, cost/token meter + daily total, suggested follow-ups, audit-trail browser, clarification & plan-confirm prompts.

### Phase 2 — Conversational workspace + visual results

- **Goal:** Multi-turn conversation with carried context (follow-ups work), interactive charts + summary tables rendered from results, suggested follow-up questions, and cost/token meter with running daily total.
- **Independent slices (parallel build units):**
  - `memory-graph` (backend) — conversation history in state + persisted per session; planner/codegen consume prior turns. Deps: none (extends Phase 1 graph).
  - `viz-result` (backend) — structured result envelope (scalar | table | chart-spec) emitted by the graph; chart spec is Vega-Lite JSON built locally from aggregates. Deps: none.
  - `cost-meter` (backend) — token + cost capture per query, daily aggregate endpoint. Deps: none.
  - `frontend-results` (frontend) — wire chart renderer, table renderer, follow-up chips, cost meter into the real UI (replacing the Phase 1 stubs). Deps: codes against extended [api.md](api.md).
- **Key surfaces / files:** `src/graph/*`, `src/analysis/viz.py`, `src/api/sessions.py`, `src/api/cost.py`, `frontend/src/components/Chart.tsx`, `frontend/src/components/ResultTable.tsx`, `frontend/src/components/FollowUps.tsx`, `frontend/src/components/CostMeter.tsx`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest` then `cd frontend && pnpm build && pnpm exec playwright test`.
- **How the user tests it:** Ask a question, then a follow-up ("now by region") — it works without restating the dataset. See a rendered chart and table. Click a suggested follow-up chip. Watch the cost meter and daily total update.

### Phase 3 — File library, cross-file compare, Excel, audit trail

- **Goal:** Manage a library of multiple datasets, compare across files, load multi-sheet Excel, browse the full audit trail (every query + code + result), and an explicit clarification/plan-confirm gate when a question is genuinely ambiguous.
- **Independent slices (parallel build units):**
  - `library-multi` (backend) — list/select/delete datasets; multi-dataset query context; multi-sheet Excel ingestion into the profiler. Deps: none.
  - `audit-clarify` (backend) — audit-trail query endpoint; conditional `clarify` node in the graph (asks a question only when ambiguous) and a `plan_confirm` interrupt. Deps: none.
  - `frontend-library` (frontend) — library sidebar, file picker for compare, Excel sheet selector, audit browser, clarify/plan-confirm UX (replacing the Phase 1/2 stubs). Deps: codes against extended [api.md](api.md).
- **Key surfaces / files:** `src/data/excel.py`, `src/api/datasets.py`, `src/api/audit.py`, `src/graph/nodes.py`, `frontend/src/components/Library.tsx`, `frontend/src/components/AuditTrail.tsx`, `frontend/src/components/ClarifyPrompt.tsx`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest` then `cd frontend && pnpm build && pnpm exec playwright test`.
- **How the user tests it:** Upload several files (incl. a multi-sheet Excel), select two and ask a cross-file question, browse the audit trail, and hit an ambiguous question to see the clarify prompt.
