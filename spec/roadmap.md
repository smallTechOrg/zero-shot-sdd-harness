# Roadmap

---

## What This Agent Does

**Local CSV Analyst** is a personal, browser-based data-analysis agent. The user uploads a CSV (typically up to ~100MB / hundreds of thousands of rows) and asks plain-English questions about it. The agent behaves like a code-executing analyst: it sketches a short plan, writes real pandas code, runs that code **locally on the full dataset**, inspects the result, and iterates — retrying a different approach when an attempt fails — then returns a plain-English answer alongside an interactive chart and a summary table, with the actual code shown collapsibly. Every run is saved as a timestamped, reproducible audit trail of exactly what code ran and what it produced.

## Who Uses It

A single technical power-user (a data-literate individual — analyst, engineer, founder) who keeps their own CSV/Excel files locally and uses the tool often. They trust answers enough to act on them, want to see the code, and care that their data never leaves the machine.

## Core Problem Being Solved

Today this person either writes pandas by hand in a notebook for every ad-hoc question (slow, repetitive) or pastes data into a cloud LLM (privacy risk, and the LLM can't run code over the full file so it guesses or samples). This agent removes both: it writes and runs the pandas itself over the **full local file**, while only schema + a few sample rows + the question ever reach the LLM — never the data.

## Success Criteria

- [ ] A user can upload the sample `olist_orders_dataset.csv`, ask "How many orders are there per order_status?", and get a correct plain-English answer + bar chart + summary table within ~30s, against the real Gemini API.
- [ ] The full dataset is loaded for execution; the LLM only ever receives schema (column names + dtypes), a small sample (≤ 20 rows), and the question — the raw file is never sent to the model (assertable: the prompt string contains no full-data rows).
- [ ] When the first generated code attempt raises an exception, the agent feeds the error back, regenerates a corrected approach, and succeeds within a bounded retry cap (default 3 attempts) — surfaced to the user as visible retry steps.
- [ ] Every run is persisted with its plan, every code attempt + result/error, the final answer, chart spec, and table — re-openable as a complete audit trail.
- [ ] The live plan, each execution step, and any retry-with-error stream to the UI as the run progresses (not just a final blob).

## What This Agent Does NOT Do (Out of Scope)

- No cloud data upload — data never leaves the local machine; only schema/samples/question go to the LLM.
- No external integrations (no Slack, no warehouses, no cloud storage) — standalone.
- No multi-user / auth / sharing — single local user.
- No write-back to the source files — read-only analysis.
- No arbitrary shell or network access inside the code sandbox — pandas/numpy over the loaded DataFrame only.
- No Excel parsing in Phase 1 (CSV only; `.xlsx` is a later phase).
- v1 does not auto-tune models or learn from feedback.

## Key Constraints

- **Privacy (HARD):** raw dataset rows never cross the LLM boundary. Only column names, dtypes, ≤ 20 sample rows, and the question. Enforced and asserted in tests. See [`spec/agent.md`](agent.md#privacy-boundary).
- **Latency:** target end-to-end answer < ~30s on a ~100MB file.
- **Cost:** keep LLM usage cheap — small prompts, few tokens, default model `gemini-3.1-pro`, ≤ 3 LLM calls per run on the happy path (plan + code-gen, plus one regen per retry).
- **Stack is fixed to this boilerplate:** flat `src/` package, FastAPI + LangGraph + SQLite (SQLAlchemy 2.0 + Alembic) + Next.js static export + Gemini. SQLite **is** production here — gate tests run on SQLite. See [`spec/architecture.md`](architecture.md#stack).
- **Reliability/reproducibility:** generated code + result stored verbatim per attempt; same question over same file is reproducible.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Backend is minimal but REAL on the one core path; frontend is visually complete with clearly-labelled NON-FUNCTIONAL stubs for everything coming later. Each later phase wires a stub into real functionality.

### Phase 1 — Upload + Ask + Code-Executing Answer

- **Goal:** Upload ONE CSV → ask ONE plain-English question → the agent plans, writes & runs pandas locally over the full file (streaming plan / steps / retries), and returns a plain-English answer + interactive chart + summary table + collapsible code → the run is saved to history. Works end-to-end against the real Gemini API on the sample olist CSV.
- **Independent slices (parallel build units):**
  - `backend` (backend) — owns all of `src/` and `alembic/`: the LangGraph plan→code→execute→retry graph, the local pandas sandbox subprocess, the upload/run/steps/get API routes with SSE streaming, the `datasets` + `runs` models + migration, prompts, and the integration tests. **deps: none.**
  - `frontend` (frontend) — owns all of `frontend/`: the single analyst page (upload, question box, live step stream, answer + chart + table + collapsible code) plus the labelled stubs, and the Playwright E2E smoke test. **deps: the API contract in [`spec/api.md`](api.md) only** (a documented seam, not a code dependency — builds concurrently against the contract).
- **Key surfaces / files:**
  - backend: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/analyst/sandbox.py` (new), `src/analyst/profile.py` (new), `src/prompts/plan.md` + `src/prompts/code.md` (replace `transform.md`), `src/api/datasets.py` + `src/api/analysis.py` (new, replacing `runs.py` as the active router), `src/db/models.py`, `alembic/versions/0002_csv_analyst.py` (new), `tests/integration/test_analysis.py`, `tests/unit/...`.
  - frontend: `frontend/src/app/page.tsx`, `frontend/src/lib/api.ts`, `frontend/src/components/*` (UploadPanel, QuestionBox, StepStream, AnswerCard, ChartView, TableView, CodeAccordion, plus stub panels LibraryStub, HistoryStub, FollowUpsStub, CostStub), `frontend/tests/e2e/analyst.spec.ts`.
- **Gate command:** `uv run alembic upgrade head && uv run python -m src & sleep 4 && uv run pytest && cd frontend && pnpm build && pnpm exec playwright test` — run against the **real Gemini API** with `AGENT_GEMINI_API_KEY` from `.env`, on the production SQLite driver. (The integration suite drives the full upload→ask→answer path; Playwright drives the live `:8001/app/` UI.)
- **How the user tests it (handoff seed):**
  1. `cp .env.example .env` and ensure `AGENT_GEMINI_API_KEY=...` is set.
  2. `uv run alembic upgrade head`
  3. `cd frontend && pnpm install && pnpm build && cd ..`
  4. `uv run python -m src` → open `http://localhost:8001/app/`.
  5. Click **Upload CSV**, choose `src/data/datasets/8bc76e9e-1151-437e-95eb-727b57b674ee/olist_orders_dataset.csv`.
  6. In the question box type: *"How many orders are there for each order_status?"* and submit.
  7. **Watch the live stream:** a short plan appears, then "writing code", "running code", and the final answer — plus an interactive bar chart and a summary table, with a collapsible "Show code" section containing the pandas that ran. If the first attempt errors, a retry step shows the error and a second attempt.
  8. **Labelled stubs (NOT bugs — read "Coming soon"):** the left **Dataset Library** panel, the **History** browser, the **Suggested follow-ups** strip under the answer, and the **Tokens / cost / session total** badges. These are visible placeholders to show the vision; they become real in later phases.

### Phase 2 — Auto-Profiling + Follow-up Suggestions

- **Goal:** On upload, the file is auto-profiled (per-column type, range/min-max, distinct count, missing-value count) and the profile is shown; after each answer the agent proposes 2–3 plain-English follow-up questions the user can click to run.
- **Independent slices (parallel build units):**
  - `backend` (backend) — extend `src/analyst/profile.py` to compute the full profile on upload and persist it to `datasets.profile_json`; add a `finalize`-node step that asks the LLM (cheaply, schema-only) for 2–3 follow-ups stored on the run. **deps: none.**
  - `frontend` (frontend) — wire the **Auto-Profile** panel and the **Suggested follow-ups** strip (previously stubs) to real data; clicking a follow-up submits it as a new question. **deps: backend profile/follow-up fields in [`spec/api.md`](api.md).**
- **Key surfaces / files:** backend: `src/analyst/profile.py`, `src/graph/nodes.py` (followups step), `src/prompts/followups.md`, `src/api/datasets.py`, migration `0003_profile_followups.py`; frontend: `frontend/src/components/ProfilePanel.tsx`, `FollowUpsStrip.tsx`.
- **Gate command:** `uv run pytest tests/integration/test_profile.py tests/integration/test_followups.py` — real Gemini API via `.env`, SQLite.
- **How the user tests it (handoff seed):** upload the olist CSV → the profile panel now shows real column types/ranges/missing counts; ask a question → 2–3 clickable follow-ups appear and clicking one runs it.

### Phase 3 — Dataset Library + Resumable Sessions

- **Goal:** Uploaded datasets persist into a browsable **library** the user returns to across days; a **session** remembers conversation history + the active dataset and is resumable later.
- **Independent slices (parallel build units):**
  - `backend` (backend) — add a `sessions` table + session/turn memory (the skeleton `AgentState.messages` becomes persisted chat history); list/get endpoints for the library and sessions; pick-from-library to start/resume a session. **deps: none.**
  - `frontend` (frontend) — wire the **Dataset Library** panel (previously a stub) and a session sidebar; selecting a library dataset loads it; reopening a session restores its history. **deps: backend session/library endpoints in [`spec/api.md`](api.md).**
- **Key surfaces / files:** backend: `src/db/models.py` (`SessionRow`), `src/api/sessions.py`, `src/api/datasets.py` (list), `src/graph/runner.py` (load/persist messages), migration `0004_sessions.py`; frontend: `LibraryPanel.tsx`, `SessionSidebar.tsx`.
- **Gate command:** `uv run pytest tests/integration/test_sessions.py tests/integration/test_library.py` — real Gemini API via `.env`, SQLite.
- **How the user tests it (handoff seed):** upload two CSVs across two visits → both appear in the library; ask several questions in a session, reload the page, reopen the session → prior turns + dataset are restored and a follow-up answer respects earlier context.

### Phase 4 — Multi-file Joins & Compares

- **Goal:** The user picks 2+ datasets (or a folder treated as one dataset) and asks questions that join/compare across them; the agent writes pandas that operates over multiple DataFrames.
- **Independent slices (parallel build units):**
  - `backend` (backend) — sandbox accepts multiple named DataFrames; plan/code prompts get multi-schema context; folder-ingest groups files into one logical dataset. **deps: none.**
  - `frontend` (frontend) — multi-select in the library + a "combine as folder" affordance; the code/answer view shows which datasets a run used. **deps: backend multi-dataset run endpoint in [`spec/api.md`](api.md).**
- **Key surfaces / files:** backend: `src/analyst/sandbox.py` (multi-frame namespace), `src/prompts/plan.md`/`code.md` (multi-schema), `src/api/analysis.py`, migration `0005_run_datasets.py` (run↔dataset join); frontend: `LibraryPanel.tsx` (multi-select), `RunDatasetsBadge.tsx`.
- **Gate command:** `uv run pytest tests/integration/test_multifile.py` — real Gemini API via `.env`, SQLite.
- **How the user tests it (handoff seed):** select two related CSVs → ask a question requiring a join → the agent writes a `merge` and answers; the run records both datasets.

### Phase 5 — Full Audit-Trail History + Cost & Telemetry

- **Goal:** A full browsable run history grouped per dataset (every question, code, result, timestamp, status) with downloadable results; per-query token count + estimated cost, a running session total, a step counter, and an elapsed timer surfaced live.
- **Independent slices (parallel build units):**
  - `backend` (backend) — token/cost accounting per LLM call persisted on the run; history list/detail endpoints grouped by dataset; result-download (CSV/JSON) endpoint. **deps: none.**
  - `frontend` (frontend) — wire the **History** browser, the **Tokens / cost / session total** badges, the step counter + elapsed timer (previously stubs) to real data; add download buttons. **deps: backend history/cost endpoints in [`spec/api.md`](api.md).**
- **Key surfaces / files:** backend: `src/llm/client.py` (token capture), `src/db/models.py` (cost fields already present from Phase 1), `src/api/history.py`, `src/api/analysis.py` (download), migration `0006_history_indexes.py`; frontend: `HistoryBrowser.tsx`, `CostBadges.tsx`, `RunTimer.tsx`.
- **Gate command:** `uv run pytest tests/integration/test_history.py tests/integration/test_cost.py` — real Gemini API via `.env`, SQLite.
- **How the user tests it (handoff seed):** run several questions → open History → see every run grouped by dataset with code/result/timestamps; live badges show tokens, per-query and session cost, step count, and an elapsed timer; download a result as CSV.
