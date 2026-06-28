# Roadmap — Pandora (Private CSV Analysis Agent)

## What It Is

A personal, privacy-preserving data-analysis agent. You upload a CSV (or Excel) export, the agent auto-profiles it, and you ask plain-language questions. The agent writes and runs **real Python/pandas locally** against your data, then returns a plain-language answer, an interactive chart, and a summary table — with the exact code it ran and the per-question cost shown. Your raw data never leaves the machine; only schema, column metadata, and small computed/aggregated results are sent to the LLM.

## Who Uses It & Why

A single power user (the operator of the machine) who works with spreadsheet exports several times a day and wants fast, correct, show-the-work answers without writing code, without pasting confidential rows into a chatbot, and without paying for a heavy cloud analytics tool.

## The Problem

- General chat assistants require pasting raw rows — unacceptable for confidential data, and they truncate large files so answers are wrong on anything past the sample.
- Writing pandas by hand per question is slow and error-prone.
- BI tools are heavy, require setup, and don't answer ad-hoc plain-language questions.
- The user needs reproducibility (the exact code), cost transparency, and a record they can revisit.

## Success Criteria

- [ ] Upload a CSV up to ~100MB; it is auto-profiled (rows, columns, types, missing %, ranges) and the profile is shown.
- [ ] Ask a plain-language question; the agent generates and runs pandas **on the full dataset** (never a sample) inside a sandbox, and returns within ~30s for a typical question.
- [ ] The answer includes: plain-language text, an interactive chart, a summary table, the exact runnable code in a collapsible panel, and the per-question token + cost.
- [ ] Raw data rows are **never** sent to the LLM — verified by an automated test asserting only schema/metadata/aggregates cross the boundary.
- [ ] Generated code runs sandboxed: no network access, restricted filesystem, and enforced time + memory limits; a malicious/buggy snippet cannot read outside the dataset or hang the server.
- [ ] On a code error, the agent retries once with the error fed back, then either succeeds or returns a clear "here's what I tried and why it's stuck" message.
- [ ] Every question (text, generated code, result, tokens, cost, timestamp) is persisted and revisitable; a running daily cost total is shown.

## Out of Scope (v1)

- Multi-file joins / multiple datasets in one question — deferred (Phase 3).
- Treating a folder of files as one dataset — deferred (Phase 3).
- Cross-day persistent sessions / returning to a dataset across days / per-column user notes memory — deferred (Phase 3).
- Full plan-then-execute "iterate until right" depth with a bounded multi-step planner — Phase 1 is one capable analysis pass with a single retry-on-error; the deeper loop is Phase 4.
- A SQL execution path — pandas first; SQL deferred (Phase 4).
- Multi-user, auth, accounts, sharing, role-based access — never (single-user local tool).
- External integrations (databases, warehouses, cloud storage, Slack, etc.) — never (standalone).
- Streaming token-by-token answer text — Phase 1 streams *step* updates; token streaming is a later polish.

## Constraints

- **Privacy is cardinal:** raw rows never leave the machine. Only schema/column metadata and computed aggregate *results* go to the LLM. See [architecture.md](architecture.md#privacy-boundary).
- **Sandboxed execution:** generated pandas runs in a subprocess with no network, a restricted working directory, and CPU-time + memory caps. See [architecture.md](architecture.md#sandboxed-code-execution).
- **Cost-aware:** default to a cheap Gemini model (`gemini-2.5-flash`), minimise calls; account tokens + cost per question and a running daily total.
- **Stack is fixed** (see [architecture.md](architecture.md#stack)): Python 3.11+ / FastAPI / LangGraph / SQLite / Gemini / Next.js static export served at `:8001/app/`. Env prefix `AGENT_`; Gemini key `AGENT_GEMINI_API_KEY` (already in `.env`).
- **Files up to ~100MB; answers under ~30s.**
- Generators **extend the existing skeleton in `src/` and `frontend/` in place** — the `transform_text` capability slot is replaced, not duplicated.

## Capabilities

| Capability | Phase | File |
|-----------|-------|------|
| profile-dataset | 1 | [capabilities/profile-dataset.md](capabilities/profile-dataset.md) |
| answer-question-with-code | 1 | [capabilities/answer-question-with-code.md](capabilities/answer-question-with-code.md) |
| cost-accounting | 1 | [capabilities/cost-accounting.md](capabilities/cost-accounting.md) |
| run-history | 2 | [capabilities/run-history.md](capabilities/run-history.md) |
| follow-up-conversation | 2 | [capabilities/follow-up-conversation.md](capabilities/follow-up-conversation.md) |
| plan-then-execute (deferred) | 4 | [capabilities/plan-then-execute.md](capabilities/plan-then-execute.md) |

---

## Phases of Development

Phase names describe what they deliver. Phase 1 is the smallest first-time-right win. All gates run against the **real Gemini API** (key from `.env`) with **SQLite as the production driver**.

### Phase 1 — Upload → Profile → Ask → Answer (the core path)

**Goal:** The user uploads one CSV, sees an auto-profile + 2–3 suggested questions, asks one plain-language question, and gets back a plain-language answer + interactive chart + summary table, with the exact runnable code in a collapsible panel and the per-question + daily cost shown. Code is generated by Gemini against schema-only metadata and runs sandboxed on the **full dataset** with one retry-on-error. All deferred features appear as clearly-labelled non-functional stubs.

**Independent slices** (all independent unless noted — fan out concurrently):

| Slice | Owns (key surfaces/files) | Depends on |
|-------|---------------------------|------------|
| `db-migration` | `src/db/models.py` (replace `RunRow` with `datasets`, `questions` tables), `alembic/`, `alembic/versions/0001_*.py`, `src/domain/*.py` | none |
| `dataset-store-profiler` | `src/datasets/store.py` (save upload to disk, load DataFrame), `src/datasets/profiler.py` (profile + suggested questions + quality flags), `src/prompts/suggest.md`, `src/tools/profile.py` | none |
| `sandbox-executor` | `src/sandbox/executor.py` (subprocess runner: no network, restricted cwd, CPU+mem limits), `src/sandbox/runner_child.py` (the executed harness) | none |
| `graph-node` | `src/graph/state.py`, `src/graph/nodes.py` (replace `transform_text` with `generate_code`/`execute_code`/`summarise`/retry), `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/generate_code.md`, `src/prompts/summarise.md` | uses `sandbox-executor` + `dataset-store-profiler` by their published interface (see note) |
| `cost-accounting` | `src/llm/usage.py` (token capture from Gemini response), `src/llm/pricing.py` (per-model rates) | none |
| `api-routes` | `src/api/datasets.py` (`POST /datasets`, `GET /datasets/{id}`), `src/api/questions.py` (`POST /datasets/{id}/ask` with SSE step stream, `GET /questions/{id}`, `GET /cost/today`), `src/api/__init__.py` (register routers), `src/domain/*.py` (request/response models) | none (codes to the [api.md](api.md) contract) |
| `frontend` | `frontend/src/app/page.tsx`, `frontend/src/components/*.tsx`, `frontend/package.json` (add `recharts`, `react-markdown`, `remark-gfm`), `frontend/tests/e2e/upload-ask.spec.ts`, `frontend/playwright.config.ts` | none (codes to the [api.md](api.md) contract) |
| `observability` | `src/observability/events.py` (extend: log code-gen prompt size, exec time, tokens, cost, retry) | none |

> **Note on the `graph-node` dependency:** the executor and profiler interfaces (function signatures + return shapes) are fully specified in [architecture.md](architecture.md) and [agent.md](agent.md) **before** the build, so the graph slice codes against those signatures and integrates only at the import seam — it does not block on the other slices' internals and builds concurrently.

**Gate (all must pass):**
```
cd frontend && pnpm install && pnpm build && cd ..
uv run alembic upgrade head && uv run alembic current
uv run pytest -q
uv run python -m src &   # boots on :8001 via the documented run command
cd frontend && npx playwright test tests/e2e/ --reporter=line   # real Gemini key from .env
```
The pytest suite must include: the **privacy-boundary** assertion (no raw rows in the LLM payload — Phase 1 blocker), a **sandbox** test (network blocked, timeout enforced, fs restricted), and a **full-dataset analytical correctness** test (fixture of **50,000 rows** with a pre-computed answer that differs from any plausible sample — see [test-driven.md](../harness/patterns/test-driven.md) and [capabilities/answer-question-with-code.md](capabilities/answer-question-with-code.md)). `alembic current` must show a revision (not blank). The Playwright smoke must upload a real CSV, ask a real question, and assert the rendered answer text, a chart element, a table, the collapsible code panel, and the cost line all appear — not just HTTP 200.

**How the user tests it:**
1. Run `cd frontend && pnpm build` then `uv run python -m src` from the repo root; open `http://localhost:8001/app/`.
2. Upload a CSV (a sample `sales.csv` ships in `examples/`). The profile card appears: row/column counts, per-column type, missing %, ranges, plus 2–3 suggested questions and any data-quality flags.
3. Type a question (or click a suggestion), e.g. "What is total revenue by region?". A live step list shows "Generating code → Running code → Summarising" with a step counter and elapsed timer.
4. The answer appears: plain-language text, an interactive chart, a summary table, a collapsible "Show code & steps" panel with the copy-runnable pandas, and "This question: N tokens · ~$0.000X · Today: $0.00YZ".
5. **Labelled stubs (real on the page, visibly non-functional):** a greyed "History" panel ("Coming in Phase 2"), a disabled "Ask a follow-up" affordance ("Conversation memory — Phase 2"), a disabled "Add another file / join datasets" button ("Multi-file — Phase 3"), and a disabled "Deep analysis (plan & iterate)" toggle ("Phase 4"). Each is badged so it is never mistaken for a bug.

### Phase 2 — Revisitable History + Follow-up Conversation

**Goal:** Wire the History stub into a real, persisted, revisitable list (question · code · result · cost · timestamp), and turn the follow-up stub into real conversation memory — ask many follow-ups against the loaded dataset, each seeing prior turns within the session.

**Independent slices:**

| Slice | Owns | Depends on |
|-------|------|------------|
| `history-api` | `GET /datasets/{id}/questions` (list), `GET /questions/{id}` (detail with code+result), pagination | none |
| `conversation-memory` | conversation turns in `AgentState`, prior-turn summaries injected into code-gen context (never raw rows), `conversation_id` on `questions` | none |
| `frontend-history` | History panel (list + detail drawer), follow-up input wired, re-run-from-history | history-api + conversation-memory contracts |

**Gate:**
```
uv run pytest -q tests/integration/test_history.py tests/integration/test_followup.py
cd frontend && npx playwright test tests/e2e/history-followup.spec.ts --reporter=line
```
Must include a **stateful multi-interaction test** (ask → follow-up referencing the first answer in the *same* session; assert the second uses the first's context) and a **state-survival test** (reload the page; history list and loaded dataset still present) — guards the `DetachedInstanceError`-class bug.

**How the user tests it:** Upload, ask, ask a follow-up that references the prior answer ("now break that down by month"), reload the page — history and dataset persist; click a past question to see its code + result.

### Phase 3 — Multi-Dataset & Cross-Day Persistence

**Goal:** Multiple datasets retained across days; pick one to load; join across two datasets in a single question; per-dataset column notes the agent remembers.

**Independent slices:** `dataset-library-api` (list/select/retain datasets across sessions), `multi-dataset-join` (graph + code-gen support two named frames; privacy boundary spans both), `column-notes-memory` (persisted per-column notes injected into code-gen context), `frontend-library` (dataset switcher, join UI, notes editor — replaces the Phase-1 multi-file stub).

**Gate:**
```
uv run pytest -q tests/integration/test_multidataset.py
cd frontend && npx playwright test tests/e2e/multidataset.spec.ts --reporter=line
```
Includes a two-dataset join with a pre-computed correct answer over the **full** rows of both files, and a cross-restart test (restart the server; prior datasets still selectable).

### Phase 4 — Deep Analysis: Plan-then-Execute, Iterate-until-Right, SQL Path

**Goal:** Wire the "Deep analysis" stub into the real bounded plan-then-execute loop ([agent.md](agent.md) deferred depth): plan multi-step, execute, reflect on intermediate results, iterate up to a bounded step count until the answer holds — escalating to a stronger model only when needed. Add a SQL execution path (DuckDB) as an alternative executor selected by a router.

**Independent slices:** `planner-node` (plan + reflect nodes, bounded step counter, goal-monitoring), `model-escalation` (resource-aware routing flash→pro when stuck), `sql-executor` (sandboxed DuckDB path), `frontend-deep` (deep-mode toggle real, plan/step trace view).

**Gate:**
```
uv run pytest -q tests/integration/test_plan_execute.py tests/integration/test_sql_path.py
cd frontend && npx playwright test tests/e2e/deep-analysis.spec.ts --reporter=line
```
Includes a multi-step question a single pass cannot answer correctly, asserting the bounded loop reaches the known answer and stops; every pattern in [agent.md](agent.md) beyond the base loop is exercised; the deep-mode trace renders; drift audit on the agent surfaces passes.
