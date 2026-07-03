# Roadmap

A private, cost-aware personal data-analysis agent for a single local user.

---

## What This Agent Does

This agent lets one person put their own spreadsheets in front of an AI analyst and ask questions in plain English. The user uploads a CSV or Excel file; the agent auto-profiles it (columns, types, row count, quality flags), then answers plain-language questions about it. For each question the agent **writes real pandas code, runs that code locally against the full dataset, inspects the result, and retries on error until it has a solid answer** — then returns a plain-language answer with the key numbers, a short narrative interpretation, at least one interactive chart, a summary table, and a collapsible view of the exact code it ran. Only the dataset **schema, a few sample rows, and the question** are ever sent to the LLM; the raw rows never leave the machine.

## Who Uses It

A single, local, non-adversarial user analysing their own data on their own machine — an operator, analyst, founder, or researcher who has spreadsheets and questions but does not want to write pandas or SQL by hand. They act on the answers, so answers must be **verifiable** (the exact code and steps are always shown). There is no multi-tenant, no auth, no shared deployment.

## Core Problem Being Solved

Getting a trustworthy answer out of a spreadsheet today means either writing code (a skill barrier) or clicking through pivot tables (slow, error-prone, and opaque). Chat-only LLMs will happily hallucinate a number from a few sample rows. This agent removes the skill barrier **without** the hallucination risk: it computes the answer on the real, full dataset with code the user can read and re-run, so the user gets a spreadsheet analyst's output with an analyst's audit trail.

## Success Criteria

- [ ] A user can upload a CSV and see an accurate auto-profile (correct column names, inferred types, exact row count) within a few seconds.
- [ ] A plain-language question returns an answer whose key number **matches a full-dataset computation** (not a sampled approximation) — verified on a 50k-row fixture where sample ≠ full.
- [ ] Every answer ships with at least one rendered chart, a summary table, and the collapsible exact pandas code that produced it.
- [ ] When the agent's first generated code errors, it retries (bounded) and still returns a correct answer without the user re-prompting.
- [ ] No raw data row is ever sent to the LLM — only schema, sample rows, and the question leave the machine (assertable in logs).
- [ ] The end-to-end round-trip for a typical question completes in well under a minute on a hundreds-of-thousands-of-rows file.

## What This Agent Does NOT Do (Out of Scope)

**Never (permanent exclusions):**
- No multi-user, no authentication, no cloud/shared deployment — single local user only.
- No sending raw data rows to the LLM — only schema + sample rows + question ever leave.
- No writing back to or mutating the user's source files — analysis is read-only.
- No arbitrary internet actions, no external data fetching beyond the LLM call.

**Deferred beyond this build (vision, not in Phases 1–2):**
- Dataset **library** management: grouping datasets into projects, renaming, per-column descriptions/annotations the agent uses.
- **Multi-dataset targeting**: user picking multiple active datasets, the agent auto-figuring which file(s) a question needs, cross-file joins/compare.
- **Clarifying-question gate** before running when a question is ambiguous, and explicit **out-of-scope detection** ("I can't answer this because…").
- **Proactive follow-up suggestions** (2–3 next questions) and proactive data-quality nudges beyond the upload-time profile flags.
- **Streaming** the answer token-by-token (Phase 2 delivers discrete live step-progress, not token streaming).

## Key Constraints

- **Privacy:** raw rows stay local. Only schema (column names/types), a handful of sample rows, and the question go to Gemini. (User confirmed sample rows are acceptable.)
- **Files:** up to ~100 MB / hundreds of thousands of rows; must cope from tiny to large.
- **Latency:** a typical answer well under a minute.
- **Cost:** low Gemini spend; scale effort to the question (Phase 2 adds the cost meter and cheaper-model option).
- **Trust:** production-quality — the user acts on answers, so the exact code and steps are always shown and re-runnable.
- **Empty state:** clean — just an upload box. No bundled sample data, no guided tour.
- **Stack is fixed** (see [architecture.md](architecture.md) `## Stack`) — extend the existing `src/` skeleton in place; never create a second package.

> **Assumed:** the pandas that the LLM generates runs in a **subprocess with a wall-clock timeout** (`AGENT_EXEC_TIMEOUT_SECONDS`, default 30s) reading the dataset from its local file — this is a robustness guard against runaway generated code, not a security sandbox (the single local user is trusted and the code derives from their own question).
> **Assumed:** charts are emitted as **Vega-Lite specs with the small aggregated result embedded**; the frontend renders them with `vega-embed`. The embedded data is the aggregated answer (a few hundred rows at most), never raw rows.
> **Assumed:** Phase 1 "iterate-until-right" = **bounded retry on execution error** (`AGENT_MAX_CODE_RETRIES`, default 3). Reflection-based quality retry (re-running because the answer looks wrong even though the code ran) is deferred.
> **Assumed:** capability count is 5 across two phases (2 in Phase 1, 3 in Phase 2). This is one above the ruthless 2–4 target, chosen so the Phase-2 requirements phase meets the ≥3-capabilities floor while keeping each capability genuinely distinct.

---

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Its backend is minimal but REAL on the one core path (no fake data on the tested path). Its frontend is visually complete: real UI for the one working path PLUS clearly-labelled NON-FUNCTIONAL stubs for everything coming later. Each later phase wires those stubs into real functionality.

### Phase 1 — Ask One Dataset (First Win)

- **Goal:** A user uploads one CSV, sees an accurate auto-profile card, types one plain-language question, and gets back a real answer computed on the full data — plain-language answer + key numbers, a short narrative, at least one rendered chart, a summary table, and the collapsible exact pandas code — all real end-to-end against real Gemini. Everything else (library, sessions/memory, history, cost meter, live progress, multi-dataset, follow-ups) appears as clearly-labelled non-functional stubs.
- **Capabilities:** [`profile_dataset`](capabilities/profile_dataset.md), [`analyze_dataset`](capabilities/analyze_dataset.md).
- **Independent slices (parallel build units):**
  - `slice-db` (backend) — SQLAlchemy models (`datasets`, `runs`), the Alembic migration, and the Pydantic domain schemas. **deps: none.**
  - `slice-analysis` (backend) — pure-Python analysis modules: file loader, profiler, subprocess pandas executor, Vega-Lite chart builder. No DB, no LLM imports. **deps: none.**
  - `slice-agent-api` (backend) — the LangGraph graph (state/nodes/edges/runner), the two prompt files, and the FastAPI routers (`datasets`, `runs`) + app wiring. **deps: slice-db, slice-analysis** (imports the models and the analysis functions — serialize after those two).
  - `slice-frontend` (frontend) — the upload → profile-card → chat → answer UI plus all labelled stubs, built against the [api.md](api.md) contract. **deps: none.**
- **Key surfaces / files:**
  - `slice-db`: `src/db/models.py`, `alembic/versions/*_phase1.py`, `src/domain/dataset.py`, `src/domain/run.py`
  - `slice-analysis`: `src/analysis/loader.py`, `src/analysis/profiler.py`, `src/analysis/executor.py`, `src/analysis/charts.py`
  - `slice-agent-api`: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/generate_code.md`, `src/prompts/write_answer.md`, `src/api/datasets.py`, `src/api/runs.py`, `src/api/__init__.py`
  - `slice-frontend`: `frontend/src/app/page.tsx`, `frontend/src/app/components/*`, `frontend/package.json` (adds `vega`, `vega-lite`, `vega-embed`)
  - tests: `tests/integration/test_phase1_pipeline.py`, `tests/e2e/test_phase1_smoke.py`, fixture `tests/fixtures/sales_50k.csv`
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/integration/test_phase1_pipeline.py -q && (cd frontend && pnpm build) && uv run pytest tests/e2e/test_phase1_smoke.py -q`
  - Runs against **real Gemini** via `AGENT_GEMINI_API_KEY` in `.env` and the **production SQLite driver** (SQLite IS production here). The Playwright smoke starts the server via `uv run python -m src` against the built `frontend/out/` at `http://localhost:8001/app/` (the skill owns server lifecycle). The pipeline test uploads `sales_50k.csv` (50,000 rows, engineered so any row-sample sum differs observably from the full-data sum), asks a total/group-by question, and asserts the returned key number **equals the independently-computed full-data value** — proving the answer used all rows, not a sample.
- **How the user tests it (handoff seed):**
  1. `cd frontend && pnpm build && cd ..` then `uv run python -m src`.
  2. Open `http://localhost:8001/app/`. You see a clean empty state: one upload box, plus a greyed-out left sidebar and toolbar with clearly-labelled **"Coming soon"** stubs (Library, Projects, History, Cost meter, Multi-dataset selector).
  3. Upload a CSV. A **profile card** appears: dataset name, exact row count, and each column with its inferred type and a quality flag (e.g. "12% nulls").
  4. Type a question (e.g. *"What were total sales by region?"*) and submit. A single "Analyzing…" spinner shows while it works.
  5. You get back: a plain-language answer with the key numbers, a one-paragraph narrative, a rendered chart, a summary table, and a collapsible **"Show code"** panel with the exact pandas.
  6. **Real vs stub:** upload, profile card, question→answer+chart+table+code are all REAL. The sidebar Library/Projects/History, the cost meter, live step-by-step progress, follow-up suggestions, and the multi-dataset selector are labelled stubs — not bugs.

### Phase 2 — Sessions, History & Cost Awareness

- **Goal:** Turn the one-shot tool into a working session: the loaded dataset stays in memory and the agent remembers the conversation so follow-ups like *"now break that down by region"* work; every question is saved to a revisitable, re-runnable history; and the user sees live step-by-step progress plus a per-question and running token/cost meter with a warning before an expensive run. Wires the Phase-1 stubs (History, Cost meter, live progress) into real features.
- **Capabilities:** [`conversation_sessions`](capabilities/conversation_sessions.md), [`run_history`](capabilities/run_history.md), [`cost_and_progress`](capabilities/cost_and_progress.md).
- **Independent slices (parallel build units):**
  - `slice-sessions` (backend) — `sessions` table + session-scoped conversation history threaded into `generate_code`/`write_answer` prompts and the graph state; session endpoints. **deps: none** (extends existing tables/graph).
  - `slice-history` (backend) — history list/detail/re-run endpoints over the existing `runs` table. **deps: none.**
  - `slice-cost` (backend) — token/cost accounting in the LLM client wrapper, a cost-estimate + expensive-run warning endpoint, and Server-Sent-Events step-progress emission from the graph nodes. **deps: none.**
  - `slice-frontend` (frontend) — wire the chat memory, history panel, cost meter, and live-progress stream into the real endpoints. **deps: none** (built to the updated api.md contract).
- **Key surfaces / files:**
  - `slice-sessions`: `src/db/models.py` (add `SessionRow`), `alembic/versions/*_phase2_sessions.py`, `src/api/sessions.py`, `src/graph/state.py` (+`messages` usage), `src/prompts/*.md`
  - `slice-history`: `src/api/runs.py` (list/detail/re-run), `src/domain/run.py`
  - `slice-cost`: `src/llm/client.py` (usage capture), `src/api/cost.py`, `src/observability/events.py`, `src/api/progress.py` (SSE)
  - `slice-frontend`: `frontend/src/app/components/*` (ChatThread, HistoryPanel, CostMeter, ProgressSteps)
  - tests: `tests/integration/test_phase2_sessions.py`, `tests/integration/test_phase2_history.py`, `tests/integration/test_phase2_cost.py`, `tests/e2e/test_phase2_smoke.py`
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/integration/test_phase2_sessions.py tests/integration/test_phase2_history.py tests/integration/test_phase2_cost.py -q && (cd frontend && pnpm build) && uv run pytest tests/e2e/test_phase2_smoke.py -q`
  - Real Gemini + production SQLite. The sessions test asks a question, then a follow-up that only resolves correctly if the prior turn is in context (e.g. *"now just the top one"*), and asserts the follow-up answer references the earlier result. The cost test asserts a non-zero token count and a dollar estimate are recorded per run. The history test asserts a saved run can be re-fetched and re-run against the current data.
- **How the user tests it (handoff seed):**
  1. Rebuild and run as in Phase 1.
  2. Upload a dataset, ask a question, then ask a **follow-up without repeating context** ("now break that down by month") — the answer builds on the previous turn.
  3. Watch the **live progress** update through "Planning… → Running code… → Writing answer…" (retries show "Retrying…").
  4. See the **cost meter** show tokens + estimated $ for that question and a running session total; ask a big question and see the **"this may be expensive"** warning first.
  5. Open the **History** panel, click a past question, see its saved answer/chart/code, and hit **Re-run** to run it again against the current data.
  6. **Real vs stub:** sessions, history, cost meter, live progress are now REAL. The Library/Projects/rename/annotations and multi-dataset selector remain labelled stubs (deferred beyond this build).
