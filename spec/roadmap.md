# Roadmap

## What This Agent Does

A local web app where a user uploads a spreadsheet (CSV in Phase 1; Excel later) and asks questions about it in plain English. The agent computes the **real** answer over the **actual** uploaded data — it never guesses or hallucinates a number — and returns:

1. A plain-language explanation of the answer.
2. The exact analysis code it ran (pandas/Python) to get that answer.
3. The intermediate steps / captured output of running that code.

The agent works by sending the LLM only the dataframe **schema + a small profile/sample** (never the full raw dataset), asking it to write pandas code, then **executing that code locally** over the full dataframe in a constrained environment. The computed result and the code are surfaced together.

## Who Uses It

A non-programmer or lightly-technical analyst who has a data file and a question, wants a trustworthy answer (one they can verify because the code is shown), and is unwilling to upload sensitive raw data to a third-party analytics service.

## Core Problem

Two unmet needs collide:
- **Trust:** General-purpose chatbots will happily fabricate statistics about a file. Users cannot tell a computed answer from an invented one.
- **Data locality:** Pasting a whole dataset into a hosted tool leaks it. Users want answers without their raw rows leaving their machine.

This agent solves both: answers are computed by code that runs locally on the full dataset, only the schema + a tiny sample is sent to the LLM, and the code is shown so the answer is auditable.

## Success Criteria

- [ ] A user can upload a CSV and ask a question through the web UI at `http://localhost:8001/app/` and receive a correct, computed answer with no manual setup beyond starting the server.
- [ ] The answer is computed by pandas code executed over the user's actual uploaded data — verifiable by inspecting the surfaced code, which references the real column names.
- [ ] The executed analysis code and its captured output are always shown alongside the plain-language answer.
- [ ] The raw uploaded dataset is never transmitted to any external service; only the schema + a bounded sample/profile is sent to the Gemini API. The raw file and parsed dataframe live only on the local filesystem and local SQLite.
- [ ] When generated code raises an error, the agent feeds the error back to the LLM and retries (bounded), rather than surfacing a raw stack trace as the answer.

## Out of Scope (for v1 / explicitly deferred)

- Excel (`.xlsx`) upload — Phase 2.
- Large files (100k+ rows): chunked/sampled profiling, memory guards, execution timeouts tuned for scale — Phase 3.
- Multiple files / joins across files — deferred (post-v1, not scheduled below).
- Charts / visualizations — deferred (post-v1).
- Persistent query-history browsing UI — deferred (post-v1).
- Authentication, multi-user accounts, deployment hardening — out of scope entirely.
- A perfect/secure code sandbox — the local execution environment is a *practical* sandbox (restricted builtins, no network, no filesystem writes, timeout), not a security boundary against a hostile LLM. See `spec/architecture.md` for the honest risk note.

## Capabilities

See `spec/capabilities/index.md`. The product has **three** capabilities total:

1. `ingest_dataset` — accept and parse an uploaded data file into a local dataframe + schema/profile.
2. `analyze_question` — turn a natural-language question into executed pandas code over the dataframe and a computed answer.
3. `present_result` — surface the answer, the executed code, and the intermediate steps to the user.

All three are exercised in Phase 1 (CSV path). Later phases broaden `ingest_dataset` (Excel, large files) without adding new capabilities.

---

## Phases of Development

The build extends the wired baseline in place. The capability slot `transform_text` (`src/graph/nodes.py`, `src/prompts/transform.md`, `frontend/src/app/page.tsx`) is **replaced** by the data-analysis flow. The DB is local SQLite (honoring the data-locality constraint), so every gate runs `alembic upgrade head` + `pytest` against the same SQLite driver used in production, with the **real Gemini API** via `.env` (`AGENT_GEMINI_API_KEY`).

> **Assumed:** Production database is local SQLite (per hard constraint #1 — local only). Therefore tests run against SQLite, which IS the production driver here; the tech-stack "tests use the production driver" rule is satisfied. No PostgreSQL is introduced.

### Phase 1 — Upload one CSV, ask one question, get a computed + explained + code-shown answer

**Goal:** A user opens `http://localhost:8001/app/`, uploads a CSV file, types one natural-language question, and gets back a correct answer computed by pandas over their actual data, in plain language, **with the executed code and its captured output shown**. Backend is minimal but fully real on this path (real Gemini, real pandas execution over the user's uploaded rows; no fake data). Reasonable file sizes only (up to a few thousand rows).

**Independent slices** (default independent; disjoint file surfaces so parallel generators never touch the same file):

- **Slice A — data layer & ingest core** (owns: `src/db/models.py`, `alembic/versions/0002_*.py`, `src/datasets/__init__.py`, `src/datasets/storage.py`, `src/datasets/profile.py`, `src/domain/dataset.py`). Defines the `datasets` and `analyses` tables; local file storage under `data/uploads/`; CSV → pandas parse; schema + profile/sample extraction. **No dependency** — pure local data code, builds first.
- **Slice B — analysis graph + sandbox** (owns: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/analyze.md`, `src/execution/__init__.py`, `src/execution/sandbox.py`). Replaces the `transform_text` node with the code-interpreter loop: generate-code → execute-locally → self-correct retry → finalize. **Depends on Slice A** — B imports `src/datasets/` functions and `src/domain/dataset.py` types. Build A first, then B.
- **Slice C — API surface** (owns: `src/api/datasets.py`, `src/api/analyses.py`, `src/api/__init__.py` (router registration only), `src/domain/analysis.py`). Upload endpoint, ask/run endpoint, fetch-result endpoint. **Depends on Slice A** (dataset storage) and **Slice B** (runner). Wired last among backend slices.
- **Slice D — frontend** (owns: `frontend/src/app/page.tsx`, `frontend/src/app/components/*`). Real upload area + question input + result view (answer + code block + steps) for the CSV path, PLUS clearly-labelled non-functional stubs for Excel, charts, and history. **No code dependency** on backend slices — talks to the documented API contract in `spec/api.md`; builds fully in parallel.
- **Serialized tail — observability + README + transform-slot cleanup.** After A–D land: confirm each new operation (upload, profile, LLM call, code execution, retry) emits a structured log line via `src/observability/events.py`; delete the now-unused `src/prompts/transform.md` and stale `transform`-only tests; update `README.md` with the new run path and `AGENT_GEMINI_API_KEY`. (Shared files: `README.md`, `src/observability` usage, `src/api/__init__.py` final wiring — applied once, serialized.)

**Dependency order:** A → B → C (serialize on the declared deps); D fully parallel; observability/README serialized last.

**Key surfaces/files:** see slice ownership above. New Python dep: `pandas` added to `pyproject.toml` `[project.dependencies]`.

**Gate (exact, real Gemini via `.env`):**
```
uv run alembic upgrade head
uv run pytest tests/phase1 -q
cd frontend && pnpm build && cd ..
uv run python -m src        # then the live smoke below, against the running server
```
Live smoke (part of the gate): `curl -s http://localhost:8001/health` returns 200. The integration test in `tests/phase1/` uploads a small fixture CSV via the API, asks a question with a known numeric answer (e.g. "what is the average of column X"), and asserts the response contains (a) an `answer` whose `result_value` matches the computed truth, (b) a non-empty `code` field referencing a real column name, and (c) non-empty `steps`. This test calls the real Gemini API and **skips only if `AGENT_GEMINI_API_KEY` is unset — a skip BLOCKS the gate.**

**How the user tests it:**
1. Set `AGENT_GEMINI_API_KEY` in `.env`.
2. Run `cd frontend && pnpm build`, then `uv run alembic upgrade head`, then `uv run python -m src`.
3. Open **http://localhost:8001/app/** (note the port, the `/app/`, and the trailing slash).
4. Click the upload area and choose a CSV (a small sales/employees file works well).
5. Type a question, e.g. "What is the average salary?" or "How many rows are there per department?" and submit.
6. Expect: a plain-language answer, AND below it a panel showing the pandas code that was run and its captured output (the intermediate steps).
7. **Labelled stubs (not bugs):** an "Excel (.xlsx)" option on the upload control, a "Visualize" / chart toggle, and a "History" panel are visible but greyed-out and tagged **"Coming soon"** — intentional non-functional placeholders showing the roadmap.

### Phase 2 — Excel (`.xlsx`) upload

**Goal:** The user can upload an Excel file (first sheet) and run the same analysis flow. The Phase 1 "Excel — coming soon" stub becomes real.

**Independent slices:**
- **Slice A — ingest extension** (owns: `src/datasets/storage.py`, `src/datasets/profile.py`): detect `.xlsx`, read via `pandas.read_excel` (first sheet), reuse the existing profile path. No new tables.
- **Slice B — frontend** (owns: `frontend/src/app/page.tsx` upload control): enable the `.xlsx` option, remove its "coming soon" label.
- **Serialized tail:** `pyproject.toml` gains `openpyxl` in `[project.dependencies]`; README + observability delta.

**Gate:**
```
uv run alembic upgrade head
uv run pytest tests/phase2 -q
```
Integration test uploads an `.xlsx` fixture and asserts the same computed-answer + code + steps contract as Phase 1, against real Gemini.

**How the user tests it:** open `http://localhost:8001/app/`, upload an `.xlsx`, ask a question, expect the same answer + code + steps view as for CSV.

### Phase 3 — Large-file scaling (100k+ rows)

**Goal:** A 100k+ row file uploads, profiles, and answers without exhausting memory or timing out. Engineering-heavy, deliberately isolated here.

**Independent slices:**
- **Slice A — profiling at scale** (owns: `src/datasets/profile.py`): bounded sampling for the LLM-facing profile (sample N rows for the sample block, compute column stats over the full frame), row-count + memory guards, configurable caps via `AGENT_MAX_ROWS` / `AGENT_PROFILE_SAMPLE_ROWS`.
- **Slice B — execution hardening** (owns: `src/execution/sandbox.py`): per-run timeout and memory ceiling tuned for large frames; clear error surfaced if exceeded.
- **Slice C — frontend** (owns: `frontend/src/app/components/*`): progress/loading state for large uploads and long-running analyses.

**Gate:**
```
uv run pytest tests/phase3 -q
```
Test ingests a generated 100k-row fixture, runs an aggregation question against real Gemini, and asserts a correct computed answer returns within the configured timeout without OOM.

**How the user tests it:** upload a large CSV (100k+ rows), ask an aggregation question, expect a correct answer within a few seconds and a visible progress indicator while it runs.

### Later (deferred, not yet scheduled)

Charts/visualizations, multi-file joins, and a persistent query-history browsing UI are out of v1 scope. Their Phase 1 stubs stay labelled "coming soon" until scheduled.
