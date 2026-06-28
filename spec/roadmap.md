# Roadmap

---

## What This Agent Does

A personal data-analysis agent for deep, multi-day exploration of a power-user's own
spreadsheet exports. The user uploads a CSV/Excel file, then asks question after question
in plain language; the agent answers with prose plus key numbers, an interactive chart,
and a summary view of the exact code it ran. It runs a genuine agentic loop — plan,
generate analysis code, execute it locally, verify the result, and iterate until the
answer holds (up to a step cap). A hard privacy boundary is non-negotiable: raw data rows
never leave the machine — the LLM sees only the dataset schema, small samples, and
aggregates, and the analysis code it writes runs LOCALLY against the user's data. Every
query, the exact code executed, and its result are recorded to a durable run-history
audit, so answers are reproducible.

## Who Uses It

A single technical power-user (the owner) running long, iterative analysis sessions over
their own data exports. They are comfortable reading code and numbers, value transparency
and reproducibility over hand-holding, and want to interrogate a dataset conversationally
across many turns and across days without re-loading context each time.

## Core Problem Being Solved

Ad-hoc data exploration today means hand-writing pandas/SQL for every question, losing the
thread of what was tried, and re-deriving context each session. Off-the-shelf "chat with
your data" tools ship raw rows to a cloud LLM — unacceptable for private exports. This
agent replaces the manual write-run-eyeball-retry loop with a transparent agentic one that
keeps raw data on the machine, shows its work, and keeps a durable, reproducible audit.

## Success Criteria

- [ ] A user can upload a CSV (up to ~100MB), see an auto-profile (columns, types, value
      ranges, missing-value counts), ask one plain-language question, and receive a prose
      answer + one interactive chart + the collapsible code that produced it, within ~30s.
- [ ] The raw data rows are never sent to the LLM — the only data-derived content in any
      LLM prompt is schema, a bounded sample, and aggregates; this is enforced in code and
      asserted by a test.
- [ ] The agentic loop (plan → generate code → execute locally → verify → iterate) recovers
      from a code error by regenerating and retrying, up to a configured step cap, and
      reports clearly when the cap is hit.
- [ ] Every query is recorded to the database with the question, the exact generated code,
      the result, the chart spec, and a UTC timestamp — and the run is retrievable.
- [ ] Analysis runs against the full dataset, not a sample — a numeric answer over a
      100k-row file matches a direct pandas computation over all rows.

## What This Agent Does NOT Do (Out of Scope)

- Does NOT send raw data rows to any external service, ever.
- Does NOT (in v1) join/compare multiple files, swap the active dataset mid-session, or
  treat a folder as one source — single active dataset per session in Phase 1.
- Does NOT (in v1) persist conversation memory across days or browser sessions, store
  user column annotations, maintain a derived-dataset library, or suggest follow-ups.
- Does NOT (in v1) display per-query token/cost accounting or a running daily total.
- Does NOT (in v1) connect to an external SQL database or read Excel — CSV only in Phase 1.
- Does NOT execute arbitrary user-supplied code; only LLM-generated analysis code runs, in
  a constrained local execution context.
- Is NOT a multi-user product — single power-user, single machine.

## Key Constraints

- **Privacy boundary (hard):** raw rows never leave the machine; the LLM sees only schema,
  bounded samples, and aggregates.
- **File size:** uploads up to ~100MB.
- **Latency:** target answer within ~30s per query.
- **Cost-conscious:** Gemini Flash, minimal LLM calls per query (one plan/codegen call per
  loop step, capped).
- **Stack (binding):** Python 3.12, LangGraph, Google Gemini (`gemini-2.5-flash`), FastAPI,
  SQLite via SQLAlchemy + Alembic, Next.js static export, uv. See
  [architecture.md → Stack](architecture.md#stack).

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Real on the one core
> path (upload → profile → ask → answer + chart + code, recorded to DB); everything else
> ships as clearly-labelled non-functional UI stubs so the user sees the vision.

### Phase 1 — Upload, Profile, Ask, Answer

- **Goal:** Upload one CSV → auto-profile it → ask ONE plain-language question → the agentic
  loop returns a prose answer + one interactive chart + the collapsible code it ran, with
  the run recorded to the DB. The LLM sees only schema/samples/aggregates.
- **Independent slices (parallel build units):**
  - `backend` (backend) — upload + profile + analyze endpoints, the LangGraph
    plan→codegen→execute→verify→iterate loop, local pandas execution context, datasets +
    analyses tables, Alembic migration, observability, and pytest suite. Deps: none.
  - `frontend` (frontend) — chat-style UI for the one working path plus labelled stubs;
    builds against the documented [api.md](api.md) contract. Deps: none (contract-driven).
- **Key surfaces / files:**
  - backend: `src/api/datasets.py`, `src/api/analyses.py`, `src/graph/state.py`,
    `src/graph/nodes.py`, `src/graph/agent.py`, `src/graph/edges.py`,
    `src/analysis/executor.py`, `src/analysis/profile.py`, `src/prompts/*.md`,
    `src/db/models.py`, `alembic/versions/*`, `tests/`.
  - frontend: `frontend/src/app/page.tsx`, `frontend/src/components/*`,
    `frontend/tests/e2e/*`. (Generators never touch the same file.)
- **Gate command (from project root, real Gemini via `.env`, SQLite prod driver):**
  `uv run alembic upgrade head && uv run pytest` then
  `cd frontend && pnpm build && npx playwright test tests/e2e/ --reporter=line`
- **How the user tests it (handoff seed):**
  1. `cd frontend && pnpm build` then from root `uv run python -m src`.
  2. Open `http://localhost:8001/app/`.
  3. Upload a CSV. See the auto-profile panel (columns, types, ranges, missing counts) —
     REAL.
  4. Type a question (e.g. "What's the average order value by region?") and send — REAL:
     prose answer, one interactive chart, and an expandable "Code it ran" block; the run is
     saved to the DB.
  5. Labelled NON-FUNCTIONAL stubs (visible, greyed, tagged "Coming soon"): multi-file /
     swap dataset, folder source, saved sessions / history across days, column annotations,
     derived-dataset library, follow-up suggestions, tokens & cost / daily total, SQL-source,
     Excel upload.

### Phase 2 — Persistent Sessions + Follow-ups

- **Goal:** Conversation history and the loaded dataset carry across turns and across days;
  after each answer the agent suggests 2-3 follow-up questions. Wires the "saved sessions"
  and "follow-up suggestions" stubs into real features.
- **Independent slices (parallel build units):**
  - `backend` (backend) — sessions table + turn memory threaded into agent state, follow-up
    suggestion node, session/history endpoints. Deps: none.
  - `frontend` (frontend) — session list + resume UI, multi-turn chat transcript, clickable
    follow-up chips. Deps: none (contract-driven).
- **Key surfaces / files:** backend `src/api/sessions.py`, `src/graph/nodes.py` (memory +
  suggest nodes), `src/db/models.py`, new Alembic migration, `tests/`; frontend session
  components + `tests/e2e/`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest -k "session or followup"`
  then `cd frontend && pnpm build && npx playwright test tests/e2e/ --reporter=line`.
- **How the user tests it (handoff seed):** Ask several questions in a row (each answer aware
  of prior turns); click a suggested follow-up; close the browser, reopen
  `http://localhost:8001/app/`, resume the prior session with its dataset and transcript intact.

### Phase 3 — Multi-Dataset + Annotations + Library

- **Goal:** Load multiple files, swap the active dataset, join/compare across datasets,
  attach column annotations that carry across turns, and save derived/cleaned datasets back
  to a library. Wires the multi-file, annotations, and library stubs.
- **Independent slices (parallel build units):**
  - `backend` (backend) — multi-dataset state, join/compare execution, annotations table,
    derived-dataset save/load + library endpoints. Deps: none.
  - `frontend` (frontend) — dataset switcher, annotation editor, library browser. Deps: none.
- **Key surfaces / files:** backend `src/api/datasets.py`, `src/api/library.py`,
  `src/analysis/executor.py` (multi-frame scope), `src/db/models.py`, new migration, `tests/`;
  frontend dataset/library/annotation components + `tests/e2e/`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest -k "multi or annotation or library"`
  then `cd frontend && pnpm build && npx playwright test tests/e2e/ --reporter=line`.
- **How the user tests it (handoff seed):** Upload two CSVs, switch active dataset, ask a
  question that compares both, annotate a column and confirm the annotation informs a later
  answer, save a cleaned result to the library and reload it.

### Phase 4 — Cost Visibility, Excel & SQL Sources

- **Goal:** Show per-query tokens + estimated cost and a running daily total; support Excel
  uploads and a folder-as-one-source; add an external SQL-database source (schema/aggregates
  only, same privacy boundary). Wires the remaining stubs.
- **Independent slices (parallel build units):**
  - `backend` (backend) — token/cost accounting in observability + a cost table, Excel/folder
    loaders, SQL-source adapter (read-only, schema+aggregate access). Deps: none.
  - `frontend` (frontend) — cost panel + daily total, Excel/folder upload, SQL connection UI.
    Deps: none.
- **Key surfaces / files:** backend `src/observability/cost.py`, `src/analysis/sources/*`,
  `src/api/*`, `src/db/models.py`, new migration, `tests/`; frontend cost + source components +
  `tests/e2e/`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest -k "cost or excel or sqlsource"`
  then `cd frontend && pnpm build && npx playwright test tests/e2e/ --reporter=line`.
- **How the user tests it (handoff seed):** Run a query and see token count + estimated cost
  and the day's running total; upload an `.xlsx`; point at a folder of CSVs; connect a local
  SQL database and confirm only schema/aggregates are read.
