# Architecture — Pandora (Private CSV Analysis Agent)

## System Overview

Pandora is a single-origin local web app. A FastAPI backend serves both the JSON/SSE API and the built Next.js static frontend at `http://localhost:8001/app/`. A LangGraph agent turns a plain-language question into **locally-executed pandas code** over a dataset stored on disk. The LLM (Gemini) only ever sees **schema and metadata**, never raw rows; it writes code, the backend runs that code in a **sandboxed subprocess** against the full dataset, and only the small computed result is summarised and returned.

```
Browser (Next.js @ /app/)
   │  POST /datasets (file)        ── upload ──▶  DatasetStore (disk, Parquet) + Profiler ──▶ profile JSON
   │  POST /datasets/{id}/ask (SSE) ─ question ─▶  LangGraph runner
   │                                                  │ generate_code (Gemini ← schema/metadata only)
   │                                                  │ execute_code (sandbox subprocess ← full data)
   │                                                  │ retry-on-error (once)
   │                                                  │ summarise (Gemini ← aggregate result only)
   │  ◀── SSE step events + final answer ───────────┘ persist question(code,result,tokens,cost)
   │  GET /cost/today                ── totals ──▶  SQLite (questions)
SQLite ── datasets, questions ──  Disk ── data/datasets/<id>.parquet, uploads/<id>.<ext>
```

## Components

| Component | Path | Responsibility |
|-----------|------|----------------|
| API factory | `src/api/__init__.py` | `create_app()`, lifespan `init_db()`, mounts `/app` static export, registers routers |
| Dataset routes | `src/api/datasets.py` | upload (multipart) → store + profile; fetch profile |
| Question routes | `src/api/questions.py` | ask (SSE step stream) → run agent; fetch question; daily cost |
| Dataset store | `src/datasets/store.py` | persist upload to disk, convert to Parquet, load DataFrame by id |
| Profiler | `src/datasets/profiler.py` | compute profile (rows/cols/types/missing/ranges/quality flags); Gemini suggests 2–3 questions |
| Sandbox executor | `src/sandbox/executor.py` + `runner_child.py` | run generated code in a locked-down subprocess; return result or error |
| LLM client | `src/llm/client.py`, `providers/gemini.py` | Gemini calls; returns text + usage |
| Usage/pricing | `src/llm/usage.py`, `src/llm/pricing.py` | extract token counts, compute cost |
| Graph | `src/graph/*` | the agent: state, nodes, edges, runner (see [agent.md](agent.md)) |
| DB | `src/db/models.py`, `session.py` | SQLAlchemy 2.0 models, SQLite session |
| Observability | `src/observability/events.py` | structlog JSON events per question |
| Frontend | `frontend/src/app/`, `components/` | upload, profile, ask, answer (chart/table/code), cost, labelled stubs |

The skeleton's wiring (settings singleton, DB session, graph assembly pattern, API factory, static mount, Gemini provider) is **extended in place** — the `transform_text` slot becomes the analysis capability; no second package is created. Note imports are bare (`from graph.state import ...`) because `pyproject.toml` sets `pythonpath = ["src"]`.

## Privacy Boundary

**Cardinal rule: raw data rows never leave the machine.** The boundary is enforced at the LLM-call seam.

**What crosses to Gemini (and only this):**
- Dataset **schema**: column names, inferred dtypes, the row count, the column count.
- Per-column **metadata/statistics**: null count / missing %, min/max for numerics, distinct-count and up to ~10 example *category labels* for low-cardinality string columns (labels are metadata, not data rows — see below), min/max for dates.
- The user's **question text** and prior-turn *summaries* (Phase 2+).
- For the `summarise` node: the **computed aggregate result** the sandbox produced (already small — a scalar, a grouped table capped at a configurable `MAX_RESULT_ROWS = 200`). This is the *output* of analysis, not the input rows.

**What never crosses:** the raw DataFrame, any full column of values, any row, the uploaded file bytes. Generated code references columns by name and is executed locally; only its result returns.

**Category-label nuance:** example labels for low-cardinality columns (e.g. region = North/South/East/West) are exposed because they are needed to write correct filters and are schema-level metadata, not row data. This is bounded by `MAX_CATEGORY_LABELS = 10` and only for columns with `distinct_count <= 50`. High-cardinality columns (names, emails, free text, IDs) expose **only** count/missing — never example values. The profiler tags each column `safe_to_sample_labels: bool`; the code-gen prompt receives labels only for safe columns.

**Enforcement & test:** the LLM payload is assembled exclusively from the profile object (a typed `DatasetProfile`) plus question/result — the raw DataFrame is never in scope at the call site. A Phase-1 gate test (`tests/integration/test_privacy_boundary.py`) captures the exact strings sent to Gemini for a dataset whose rows contain a unique sentinel value (e.g. a UUID in a high-cardinality column) and asserts the sentinel **never** appears in any prompt. This is a Phase-1 blocker.

## Sandboxed Code Execution

Generated pandas runs in a **separate Python subprocess** (`subprocess.run`), never `exec()` in-process. Concrete mechanism (dependency-light, single-user local — no Docker required):

- **Process isolation:** a fresh `python -m sandbox.runner_child` child per execution; the parent passes the dataset Parquet path and the code via a temp file. No agent state, no DB handle, no secrets are inherited.
- **No network:** the child installs a socket guard at startup — `socket.socket` is monkeypatched to raise, and `AGENT_*` / proxy env vars are stripped from the child environment — so `requests`/`urllib`/any socket call fails immediately. (Belt-and-braces: the child's allowed import namespace is restricted to `pandas`, `numpy`, `math`, `datetime`, `json`; `import socket`/`os.system`/`subprocess` in generated code is rejected by a static check before execution.)
- **Restricted filesystem:** the child runs with `cwd` set to a per-run temp dir; it may read **only** the one dataset Parquet path passed to it (opened by the harness, handed to the code as a ready `df`, so generated code never opens files itself) and may write **only** within its temp dir. A static check rejects `open(`, `Path(`, `os.`, `__import__`, `eval`, `exec`, dunder attribute access in generated code.
- **Time limit:** `subprocess.run(..., timeout=SANDBOX_TIMEOUT_SECONDS=25)`; on timeout the child is killed and the node returns a timeout error (well under the ~30s answer budget).
- **Memory limit:** the child calls `resource.setrlimit(RLIMIT_AS, MEMORY_LIMIT_BYTES)` (default 2 GB, configurable) at startup, so a runaway allocation raises `MemoryError` instead of swapping the machine. (POSIX/macOS/Linux — the target is a local single-user machine; documented as such.)
- **Contract:** the harness loads the Parquet into `df`, `exec`s the validated snippet in a namespace exposing only `df`, `pd`, `np`; the snippet must assign a `result` variable. The harness JSON-serialises `result` (DataFrame → records capped at `MAX_RESULT_ROWS`, plus a `chart_spec` if the code set one) to stdout. The parent reads stdout/stderr/returncode.

**Executor interface (frozen for the `graph-node` slice to code against):**
```
# src/sandbox/executor.py
def run_code(code: str, dataset_path: str) -> ExecResult
# ExecResult = { ok: bool, result: dict | None, stdout: str, error: str | None,
#                kind: "ok"|"static_reject"|"runtime_error"|"timeout"|"memory" }
```

## Dataset Storage & Profiling

- Upload saved to `data/uploads/<dataset_id>.<ext>` (raw, for re-profiling), then converted **once** to `data/datasets/<dataset_id>.parquet` — Parquet is the canonical analysis format: typed, columnar, fast to load full (no sampling), handles ~100MB comfortably.
- Excel (`.xlsx`) is read via `openpyxl` on upload and written to the same Parquet path; from then on the pipeline is format-agnostic.
- **Profiling reads the full DataFrame** (not a sample): row/col counts, per-column dtype, null count + missing %, numeric min/max/mean, date min/max, distinct counts, `safe_to_sample_labels` flag + example labels for low-cardinality columns. Quality flags: high-missing columns (>30%), constant columns, fully-duplicate rows, mixed-type columns.
- The `DatasetProfile` is persisted as JSON on the `datasets` row and is the **only** dataset information ever sent to the LLM.

## Cost & Token Accounting

- The Gemini response carries `usage_metadata` (`prompt_token_count`, `candidates_token_count`). `src/llm/usage.py` extracts these per call; `LLMClient.call_model` returns text + a `Usage` object.
- `src/llm/pricing.py` holds per-model per-1K-token rates (`gemini-2.5-flash` input/output). Cost = tokens × rate, summed across the code-gen + summarise calls for one question.
- Persisted per `questions` row: `prompt_tokens`, `completion_tokens`, `cost_usd`, model name. **Daily total** = `SELECT SUM(cost_usd) FROM questions WHERE date(created_at)=today` (server-local date), exposed via `GET /cost/today`.
- Cost-minimisation: default model `gemini-2.5-flash`; one code-gen call + one summarise call per question (two calls), no speculative calls; the retry reuses the same model with the error appended. Model escalation to `gemini-2.5-pro` is a Phase-4 concern only.

## Streaming Step Updates

`POST /datasets/{id}/ask` responds with **Server-Sent Events** (`text/event-stream`). The runner yields a step event at each node boundary: `{step: "generating_code"|"running_code"|"retrying"|"summarising", index, elapsed_ms}`, then a final `{type:"answer", ...}` event carrying the full answer payload (and an `{type:"error", ...}` on failure). The frontend renders the live step list, counter, and elapsed timer from these events; the final answer event populates the chart/table/code/cost. (Token-by-token streaming of the answer text is out of scope for v1.)

## Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Language | Python 3.11+ | matches skeleton `requires-python = ">=3.11"` |
| Agent framework | LangGraph (`langgraph>=0.1`) | graph in `src/graph/` — see [agent.md](agent.md) |
| LLM provider | Google Gemini (`google-genai`) | key `AGENT_GEMINI_API_KEY` in `.env`; provider auto-detected |
| LLM model | `gemini-2.5-flash` (default, configurable via `AGENT_LLM_MODEL`) | cheap/fast; `gemini-2.5-pro` reserved for Phase-4 escalation |
| Backend | FastAPI + Uvicorn on **port 8001** | `uv run python -m src` |
| Database | **SQLite** (`sqlite:///./data/agent.db`) | the production driver — local single-user tool; Alembic migrations |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | direct queries in nodes/handlers, no repository pattern |
| Data engine | pandas + pyarrow (Parquet), openpyxl (xlsx read) | full-dataset analysis, no sampling |
| Sandbox | subprocess + `resource.setrlimit` + socket guard + static check | no Docker; POSIX local machine |
| Frontend | Next.js 15 static export (`output: 'export'`, `basePath: '/app'`) + React 19 + Tailwind v4 | served by FastAPI at `:8001/app/` |
| Charts / markdown | `recharts`, `react-markdown` + `remark-gfm` | interactive chart; markdown-rendered LLM text |
| E2E | Playwright (chromium) in `frontend/tests/e2e/` | Phase-1 gate |
| Dep management | uv (Python) · pnpm (frontend) | |
| Observability | structlog JSON to stdout (`src/observability/events.py`) | per-question event: prompt size, exec ms, tokens, cost, retry. (LangSmith optional via `LANGCHAIN_*` env if the user sets it; structured logging is the always-on default.) |

**New Python dependencies to add to `pyproject.toml` `[project.dependencies]`:** `pandas>=2.2`, `pyarrow>=16`, `openpyxl>=3.1`, `python-multipart>=0.0.9` (FastAPI file uploads), `sse-starlette>=2.1` (SSE responses). The DB driver is stdlib `sqlite3` (no extra package), per the SQLite choice.

> **Assumed:** the deployment target is a POSIX machine (macOS/Linux) — `resource.setrlimit` and the subprocess sandbox are POSIX-oriented. This matches "a single power user who works on their own machine"; documented in the README as a requirement.

> **Assumed:** Excel `.xlsx` is in scope for upload (brief says "CSV/Excel exports") and is normalised to Parquet on upload; `.xls` (legacy) is out of scope.

> **Assumed:** observability is structured stdout logging by default; LangSmith tracing is wired only if the user provides `LANGCHAIN_API_KEY` (the brief specifies Gemini, not LangChain tracing, and does not require LangSmith). This satisfies the always-on observability rule via structured logging.
