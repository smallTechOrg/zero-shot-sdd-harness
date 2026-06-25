# Roadmap

---

## What This Agent Does

The **Data Analysis Agent** is a local, single-user web app. The user uploads a CSV (or TSV/TXT/JSON/Excel) file through the browser and asks questions about the data in plain English. A ReAct loop (Reason + Act) powered by Google Gemini reasons over the data with pandas, iterating until it can give a confident natural-language answer with optional inline charts. No code or SQL required from the user. The agent tracks each step it took, supports multi-turn conversations scoped to a set of datasets, can autonomously produce new derived datasets, and shows its own token usage and reasoning.

## Who Uses It

Data analysts, product managers, and non-technical stakeholders who have structured data sitting in files and want answers without writing code or SQL. Their goal: upload a file once, ask questions in plain English, and get correct, explainable answers in seconds.

## Core Problem Being Solved

Today these users either learn pandas/SQL, wait on an analyst, or fight with spreadsheet formulas. The agent replaces that manual analysis loop: it does the reasoning and the pandas execution itself, shows its work step by step, and returns a plain-English answer with charts — so a non-technical user gets a correct, explainable result directly.

## Success Criteria

- [ ] A user can upload a CSV through the browser in under 5 seconds and see it appear as a dataset with row/column counts.
- [ ] A user can ask an aggregation / filter / comparison question and get a correct natural-language answer (verified against the real Gemini API) in under 30 seconds.
- [ ] The ReAct loop iterates with pandas and self-corrects on execution errors, terminating on a `FINAL ANSWER:` signal or a force-finalize (max iterations / consecutive errors) — it never crashes the request.
- [ ] Multi-turn conversation works: a follow-up question in a session sees prior turns and reuses the same datasets.
- [ ] With no API key set, the app auto-engages stub mode, shows a visible yellow banner, and stays fully usable offline with plausible canned answers (a guarantee in addition to the real-key path, never a substitute for it).

## What This Agent Does NOT Do (Out of Scope)

- No authentication / multi-user / accounts — single local user only.
- No database querying — files only (CSV/TSV/TXT/JSON/Excel).
- No proactive auto-insights or scheduled analysis — every analysis is user-initiated.
- No data egress beyond the configured LLM provider — uploaded data lives on local disk and SQLite.
- No TTL / auto-expiry of datasets — they persist until explicitly deleted.

## Key Constraints

- **Single-user, local.** One agent run at a time per request; live progress polled at ~1/s.
- **File size:** the ReAct loop must answer aggregation/filter/comparison questions on datasets up to 100 MB.
- **Latency targets:** upload < 5 s; question → answer < 30 s (real Gemini).
- **Provider:** Google Gemini is the live provider (key in `.env`). OpenRouter is an alternate. Stub mode auto-engages with no key.
- **Production DB is SQLite** (via SQLAlchemy 2.0 + Alembic). This is the chosen production database for this project — SQLite IS production here; tests use an isolated SQLite copy, which is correct, not a substitute.
- **Conversation cap:** a session is limited to 20 turns.
- **Context note cap:** dataset context notes ≤ 4000 chars; compressed facts ≤ 20 per scope.

> **Assumed:** Default Gemini model is `gemini-3.1-flash-lite` (per source). It MUST be verified against the real API at the Phase 2/3 real-key gate; on a 404 (model not found) fall back to a known-good model (`gemini-2.5-flash`, the current skeleton default) and record the chosen model in `spec/architecture.md` (`## Stack`) and `README.md`. See `architecture.md` → LLM provider design.

> **Assumed:** The source capability list (C1–C32) has no **C28** — it skips from C27 to C29. This is treated as an intentional gap in the source's numbering, not a missing capability. We preserve the source's IDs verbatim (no renumber) and document the gap in `spec/capabilities/index.md`. No `C28` file is created.

---

## Phases of Development

> Four phases, derived from the source's P1–P4. Phase 1 is an OFFLINE data-layer win verified by tests + migrations (no clickable page — that is expected and stated below). Phase 2 wires the ReAct loop through the FastAPI routes and the real Analyse-tab UI, gated against the **real Gemini via `.env`** per harness rules #6/#7. Phase 3 adds live sessions / pre-flight selector & clarification + the end-to-end real-key test and the model verify/fallback. Phase 4 adds charts + derived datasets + the Database-tab ER diagram polish.
>
> Every gate runs against the **production DB driver (SQLite via `AGENT_DATABASE_URL`)**. Phase 1's gate is OFFLINE (no key). Phase 2+ gates run against the **real Gemini key in `.env`** and assert response CONTENT, not just status. An offline stub suite (`tests/unit/`, zero env, in-memory SQLite, no network) ships alongside as an ADDITIONAL guarantee — the real-key gate is always authoritative.
>
> **Slices are disjoint by file path** so parallel code-generators never touch the same file. Dependencies are declared explicitly; default is independent.

### Phase 1 — Offline data layer (the 4-table schema, domain entities, settings)

- **Goal:** The full SQLite data model exists and migrates cleanly: the 4 tables (`datasets`, `query_runs`, `conversation_sessions`, `settings`) are added to `db/models.py`, reachable via `init_db()`, covered by an Alembic migration, mirrored by Pydantic domain entities, with the new settings fields (`openrouter_api_key`, `max_iterations`) added. Verified by unit tests + a real Alembic migration against SQLite. This is a backend-only phase — there is no clickable page yet (expected). A clearly-labelled non-functional two-tab UI shell makes the vision visible.

- **Independent slices (parallel build units):**
  - `slice-1a` (backend — data layer) — the 4 SQLAlchemy models extending the existing `Base`, the Alembic migration `0002_data_analyst_tables.py`, the Pydantic domain entities, the settings additions, and unit tests for all of it. **Deps: none.**
  - `slice-1b` (frontend — visual stub shell) — the two-tab app shell (Analyse / Database tabs) in `frontend/`, replacing the transform form, with every interactive surface rendered as a clearly-labelled NON-FUNCTIONAL placeholder. **Deps: none** (pure presentational; no API calls — labels say "coming in a later phase").

- **Key surfaces / files:**
  - `slice-1a` owns: `src/db/models.py` (ADD `DatasetRow`, `QueryRunRow`, `ConversationSessionRow`, `SettingRow`; keep `RunRow`), `alembic/versions/0002_data_analyst_tables.py` (NEW), `src/config/settings.py` (ADD `openrouter_api_key`, `max_iterations`; extend `llm_provider` valid values), `src/domain/dataset.py` + `src/domain/query_run.py` + `src/domain/session.py` + `src/domain/setting.py` (NEW), `tests/unit/test_models.py` + `tests/unit/test_settings.py` + `tests/unit/test_domain.py` (NEW). Does NOT touch `db/session.py` (its `init_db()` already builds all of `Base.metadata` — new models flow in automatically; the conftest `_isolated_db` likewise picks them up).
  - `slice-1b` owns: `frontend/src/app/page.tsx` (REPLACE transform form with the two-tab shell), `frontend/src/components/AppShell.tsx` + `frontend/src/components/StubBanner.tsx` + `frontend/src/components/analyse/*` + `frontend/src/components/database/*` (NEW, all non-functional placeholders), `frontend/src/lib/*` if needed. Never touches `src/`.

- **Gate command (OFFLINE — no key required):**

  ```bash
  uv run pytest tests/unit/ -q
  uv run alembic upgrade head
  uv run alembic current
  ```
  All three from the repo root. `pytest tests/unit/` must pass with **no env vars and no network**; `alembic upgrade head` must succeed against the configured SQLite DB; `alembic current` must show a revision (proving the 4 tables exist). The DB driver is the production one (SQLite via `AGENT_DATABASE_URL`).

- **How the user tests it (handoff seed):** From the repo root run the three gate commands above and confirm: unit tests green, `alembic upgrade head` says "Running upgrade 0001 -> 0002", and `alembic current` prints `0002 (head)`. This is a **backend-only phase verified via tests + migrations — there is intentionally no clickable analysis page yet**, say so explicitly. Optionally run `python agent.py --run` and open `http://localhost:8001/app/`: the two-tab shell is visible but **every control is a labelled NON-FUNCTIONAL stub** ("Upload — coming in a later phase", etc.). Those stubs are the planned vision, not bugs.

### Phase 2 — ReAct loop + REST routes + real Analyse tab (single-dataset Q&A)

- **Goal:** The core path works end to end: upload a CSV, ask a plain-English question on a **single dataset (no sessions yet)**, the ReAct loop runs through `LLMClient` (real Gemini from `.env`), and the rendered Markdown answer + iteration/token counts + steps inspector appear in the Analyse tab. Stub mode auto-engages with no key.

- **Independent slices (parallel build units):**
  - `slice-2a` (backend — LLM providers) — extend `LLMClient`/factory to the multi-provider design: add `stub` and `openrouter` providers behind the uniform interface; auto-detect provider from whichever key is set; explicit `stub` when none; the stub branches on injected node tags. **Deps: none.**
  - `slice-2b` (backend — graph) — replace the `transform_text` graph with the ReAct `StateGraph`: `AgentState`, nodes `setup / plan_action / execute_action / finalize / force_finalize / handle_error`, edges, the sandbox namespace, the runner, prompts. **Deps: slice-2a** (the graph calls `LLMClient`; consume its public `call_model` interface — stub can stand in during dev, but the gate uses real Gemini).
  - `slice-2c` (backend — API) — the upload/datasets/ask/runs/stats/health routers + the `ok()`/`api_error()` envelope wiring and single-origin static mount. **Deps: slice-2b** for `/ask` (calls the runner) and `slice-1a` data layer (already merged). Upload/datasets/preview routes are independent of the graph.
  - `slice-2d` (frontend — Analyse tab) — wire the Analyse tab to the real API: upload card, Tables/datasets card, Conversation card (ask, rendered Markdown, steps inspector, token counts), stub banner driven by a `provider` flag. **Deps: slice-2c** (consumes the REST contract in `spec/api.md`; can be built in parallel against that contract and integrated at the gate).

- **Key surfaces / files:**
  - `slice-2a` owns: `src/llm/client.py` (extend factory), `src/llm/providers/base.py` + `src/llm/providers/stub.py` + `src/llm/providers/openrouter.py` (NEW), `src/llm/providers/gemini.py` (model default note only). `tests/unit/test_providers.py` (NEW).
  - `slice-2b` owns: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py` (REPLACE the transform graph in place), `src/graph/sandbox.py` (NEW), `src/prompts/plan_action.md` + `src/prompts/finalize.md` (NEW; the old `prompts/transform.md` is removed by this slice). `tests/unit/test_graph_stub.py` (NEW).
  - `slice-2c` owns: `src/api/__init__.py` (register new routers), `src/api/upload.py` + `src/api/datasets.py` + `src/api/ask.py` + `src/api/stats.py` (NEW), `src/api/health.py` (extend `/health` with `provider`), `src/api/runs.py` (ADD `/runs/current`; keep existing), `src/domain/*` request/response models as needed. `tests/integration/test_ask_real.py` + `tests/e2e/test_golden_path.py` (NEW, real Gemini). `tests/unit/test_api_stub.py` (NEW, offline). NOTE: this slice removes the boilerplate `/runs` POST contract only if it conflicts — otherwise leave it; the canonical analysis route is `/ask`.
  - `slice-2d` owns: `frontend/src/app/page.tsx`, `frontend/src/components/analyse/*` (REPLACE the Phase-1 stubs with real components for upload + tables + conversation), `frontend/src/lib/api.ts` (NEW). Never touches `src/`. The Database tab and the session sidebar stay labelled stubs in this phase.

- **Gate command (REAL Gemini from `.env`, per rules #6/#7):**

  ```bash
  uv run pytest tests/unit/ -q
  uv run pytest tests/integration/ tests/e2e/ -q
  ```

  The first line is the offline stub suite (zero env, in-memory SQLite, no network) — an additional guarantee. The second line is the **authoritative real-key gate**: it requires `AGENT_GEMINI_API_KEY` in `.env`, drives the full upload → ask → answer journey through `TestClient` against the real Gemini, and asserts on real response **content** (the answer is non-empty Markdown, the run status is `completed`, steps were recorded). Plus a **live-server smoke**: `python agent.py --run` (runs migrations + frontend build + starts uvicorn on :8001), then `curl http://localhost:8001/health` and one real `/ask` round-trip returning real AI output. The model is verified here (see `architecture.md`); 404 → fall back to `gemini-2.5-flash` and record it.

- **How the user tests it (handoff seed):** From the repo root run `python agent.py --run` (it builds the frontend and starts the server), then open `http://localhost:8001/app/`. Upload a small CSV (it appears under "Tables" with rows×cols), type a question like "What is the average of column X?" and click Ask. Expect: a spinner, then a rendered Markdown answer, iteration + token counts, and an expandable Steps inspector showing the pandas the agent ran. **Real surfaces:** upload, Tables list, ask/answer/steps, token counts, stub banner. **Labelled stubs (still):** the Database tab, the sessions sidebar, follow-up suggestions, charts, derived datasets — coming in Phase 3/4.

### Phase 3 — Live sessions, multi-turn, pre-flight selector & clarification, suggestions

- **Goal:** Multi-turn conversations scoped to datasets work: a session carries history, the pre-flight clarification check (C26) can ask a clarifying question, the dataset selector (C19) picks which datasets to load for multi-dataset questions, follow-up suggestions appear, and the session sidebar is fully functional. The end-to-end real-key test passes and the Gemini model is verified/fallback-confirmed.

- **Independent slices (parallel build units):**
  - `slice-3a` (backend — sessions API) — `/sessions` CRUD + `/datasets/{id}/sessions`, session-scoped run creation, the 20-turn cap, multi-turn history assembly. **Deps: Phase-2 `/ask`** (extends it; same file, so this slice OWNS `src/api/ask.py` + `src/api/sessions.py` for Phase 3).
  - `slice-3b` (backend — pre-flight + graph-adjacent) — `check_clarification` (C26), `select_datasets` (C19), `generate_suggestions`, session DataFrame cache (C27) in `setup`. **Deps: slice-2b graph** (extends `setup`/runner; OWNS `src/graph/preflight.py` + `src/graph/suggestions.py` + the `setup` cache logic + `src/prompts/clarify.md` + `src/prompts/select.md` + `src/prompts/suggest.md`).
  - `slice-3c` (backend — memory API) — `/memory` GET/PATCH + the global-memory injection into `plan_action`. **Deps: none** beyond the data layer (`settings` table). OWNS `src/api/memory.py` + the memory-read helper.
  - `slice-3d` (frontend — sessions + conversation polish) — sessions sidebar (list/resume/rename/new/delete/bulk), clarification turns (amber, re-submit with `skip_clarification`), suggestion chips, collapsible turns (C32), live progress bar from `/runs/current`. **Deps: slice-3a + slice-3b** (consumes their REST contracts). OWNS `frontend/src/components/analyse/SessionSidebar.tsx` + conversation components.

- **Key surfaces / files:** `slice-3a` → `src/api/ask.py`, `src/api/sessions.py`, `tests/integration/test_sessions_real.py`. `slice-3b` → `src/graph/preflight.py`, `src/graph/suggestions.py`, `src/graph/nodes.py` (setup cache only), `src/prompts/{clarify,select,suggest}.md`, `tests/integration/test_preflight_real.py`. `slice-3c` → `src/api/memory.py`, `src/graph/nodes.py` is NOT touched by 3c (memory read is a helper in `src/graph/memory.py` NEW owned by 3c; 3b's `plan_action` imports it — declared dependency, 3b owns the import line, 3c owns the helper file). `slice-3d` → `frontend/src/components/analyse/*` only.
  - **Conflict note:** `src/graph/nodes.py` is touched by both 3b (setup cache) and indirectly by 3c's helper. Resolve by: 3b OWNS all edits to `nodes.py`; 3c only ADDS `src/graph/memory.py` and exposes `get_memory_block()`; 3b imports it. This keeps file ownership disjoint.

- **Gate command (REAL Gemini from `.env`):**

  ```bash
  uv run pytest tests/unit/ -q
  uv run pytest tests/integration/ tests/e2e/ -q
  ```

  The integration suite now includes a **multi-turn real-key test**: create a session, ask Q1, ask a follow-up Q2 that depends on Q1's context, assert Q2's answer reflects the prior turn (real Gemini content). Plus a clarification test (ambiguous question → `type: "clarification"`) and a selector test (two datasets → correct subset loaded). Live-server smoke re-run (`python agent.py --run` then `curl` `/health` + a real `/ask`). The Gemini model is confirmed here.

- **How the user tests it (handoff seed):** Run `python agent.py --run` and open `http://localhost:8001/app/`. Create a New session, upload two CSVs, ask a question — answer appears; click a follow-up suggestion chip; ask an ambiguous question and see an amber "Needs clarification" turn with a re-submit. Rename and resume sessions from the sidebar. **Real surfaces now:** sessions sidebar, multi-turn, clarification, suggestions, dataset selection, live progress, project-notes/memory modal. **Labelled stubs (still):** inline charts and derived-dataset/save_dataset features, the Database-tab ER diagram — coming in Phase 4.

### Phase 4 — Charts, derived datasets, Database-tab ER diagram

- **Goal:** Inline charts render from the agent's Plotly figures, the agent can autonomously persist derived datasets via `save_dataset` (with lineage + staleness + re-derive), NL data cleaning (preview + apply) works, on-demand dataset notes + compression run, and the Database tab shows the full ER diagram with inferred FK edges and the table-description panel.

- **Independent slices (parallel build units):**
  - `slice-4a` (backend — charts + derived datasets) — capture Plotly figures as JSON in `execute_action`, `save_dataset` in the sandbox, derived-dataset registration + lineage + staleness, `/datasets/{id}/re-derive`. **Deps: slice-2b graph** (OWNS the sandbox + `execute_action` chart capture + `src/graph/derived.py`).
  - `slice-4b` (backend — cleaning + notes/compression) — `/datasets/{id}/clean` + `/clean/apply` (C24), `/datasets/{id}/describe` → `describe.py` (C30), `compress.py` (C31). **Deps: data layer + LLMClient.** OWNS `src/graph/describe.py` + `src/graph/compress.py` + the clean routes in a NEW `src/api/datasets_ops.py` (so it does not collide with 2c's `src/api/datasets.py`).
  - `slice-4c` (frontend — Database tab + charts render) — the Database tab ER diagram (`renderERDiagram`, `_erFkLinks`), the table-description panel, inline chart rendering in conversation turns, derived/stale badges + re-derive button, clean modal. **Deps: slice-4a + slice-4b** REST contracts. OWNS `frontend/src/components/database/*` + chart-render components in `frontend/src/components/analyse/*`.

- **Key surfaces / files:** `slice-4a` → `src/graph/sandbox.py` (chart capture + save_dataset), `src/graph/derived.py` (NEW), `src/api/datasets.py` (ADD `/re-derive` — owned by 4a in Phase 4), `tests/integration/test_derived_real.py`, `tests/e2e/test_charts.py`. `slice-4b` → `src/graph/describe.py` (NEW), `src/graph/compress.py` (NEW), `src/api/datasets_ops.py` (NEW), `src/prompts/{describe,compress,clean}.md` (NEW), `tests/integration/test_clean_real.py`. `slice-4c` → `frontend/src/components/database/*`, `frontend/src/components/analyse/ChartRender.tsx`. Never touches `src/`.

- **Gate command (REAL Gemini from `.env`):**

  ```bash
  uv run pytest tests/unit/ -q
  uv run pytest tests/integration/ tests/e2e/ -q
  ```

  The e2e suite includes a **real-key chart test** (ask a question that yields a chart → assert a Plotly figure JSON is captured and returned) and a **derived-dataset test** (a question that triggers `save_dataset` → a new derived dataset is registered with lineage). Plus a **visual smoke**: `python agent.py --run`, drive `/ask` to produce a chart and `curl` the page / API to confirm chart JSON and the ER-diagram dataset payload are present.

- **How the user tests it (handoff seed):** Rebuild and run; ask a question that warrants a chart (e.g. "show the distribution of column X") — an inline chart renders. Ask something that creates a new table (e.g. "create a cleaned version with nulls dropped and save it") — a Derived dataset appears under Tables with a green badge. Open the Database tab: the ER diagram shows each dataset as a card with inferred FK edges; click a card to see its description, keys, columns, and preview; edit context notes; click "Generate notes". **All surfaces are now real.** No remaining stubs.
