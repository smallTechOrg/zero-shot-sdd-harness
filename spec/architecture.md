# Architecture

## System Overview

A single-origin local web application. A FastAPI backend serves both a JSON API and a statically-exported Next.js frontend (mounted at `/app`) on port **8001**. The user uploads a data file; the backend parses it locally into a pandas dataframe, persists the raw file to the local filesystem and metadata to local SQLite. When the user asks a question, a LangGraph agent generates pandas code from the dataframe's **schema + a small profile/sample**, executes that code **locally** over the full dataframe in a constrained environment, self-corrects on errors, and returns the computed answer together with the executed code and intermediate steps.

The only outbound network call is to the **Gemini API**, and it carries only the schema + a bounded sample/profile + the user's question — never the raw dataset.

## Components

| Component | Path | Responsibility |
|-----------|------|----------------|
| API layer | `src/api/` | HTTP endpoints (datasets, analyses, health), `ok()`/`api_error()` envelopes, static `/app` mount |
| Domain models | `src/domain/` | Pydantic request/response + internal DTOs (`dataset.py`, `analysis.py`, existing `run.py`) |
| Dataset ingest | `src/datasets/` | Local file storage (`storage.py`), parse + schema/profile extraction (`profile.py`) |
| Analysis graph | `src/graph/` | LangGraph code-interpreter loop (state, nodes, edges, agent, runner) — see `spec/agent.md` |
| Code execution | `src/execution/sandbox.py` | Runs LLM-generated pandas code locally with restricted builtins, no network, no FS writes, timeout |
| LLM client | `src/llm/` | Provider abstraction; Gemini provider (`gemini-2.5-pro`) |
| Persistence | `src/db/` | SQLAlchemy models + session; local SQLite |
| Config | `src/config/settings.py` | `AGENT_`-prefixed settings (DB URL, LLM provider/model/key) |
| Observability | `src/observability/events.py` | Structured logging — carried by every phase |
| Frontend | `frontend/src/app/` | Upload area, question input, result view (answer + code + steps), labelled stubs |

## Data Flow (how data-locality is honored)

```
┌────────────┐   upload CSV    ┌─────────────────────────────────────────────┐
│  Browser   │ ───────────────▶│ POST /datasets                              │
│ (frontend) │                 │  storage.save() → data/uploads/<id>.csv     │
│            │                 │  profile.build() → pandas.read_csv (local)  │
│            │                 │   → schema + dtypes + small sample/profile  │
│            │◀── dataset_id ──│  datasets row written to local SQLite       │
└────────────┘                 └─────────────────────────────────────────────┘
       │ ask question
       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ POST /analyses { dataset_id, question }                                       │
│                                                                               │
│  runner loads the FULL dataframe locally from data/uploads/<id>.csv           │
│  graph.generate_code:                                                         │
│      ┌─────────────────── sent to Gemini ──────────────────┐                  │
│      │ schema + dtypes + SMALL sample/profile + question     │ ── network ──▶ Gemini API
│      └───────────────────────────────────────────────────────┘              │ (gemini-2.5-pro)
│      ◀── generated pandas code ───────────────────────────────────────────────┘
│  graph.execute_code:  run code LOCALLY over the FULL df in sandbox            │
│      → result + captured stdout (intermediate steps)                          │
│  on error → graph.generate_code again with the error (bounded retries)        │
│  graph.finalize: build answer + persist analyses row to local SQLite          │
└─────────────────────────────────────────────────────────────────────────────┘
       │ GET /analyses/{id}
       ▼
   answer (plain language) + executed code + steps  ── rendered in browser
```

**The raw dataframe never leaves the machine.** Only the schema, dtypes, and a bounded sample/profile (default a few sample rows + per-column summary stats) plus the question are sent to Gemini. The full dataframe is loaded and computed over only inside the local process; results are persisted only to local SQLite and the local filesystem.

## Code Execution Safety (honest risk note)

The sandbox (`src/execution/sandbox.py`) runs LLM-generated code with:
- a restricted `__builtins__` (no `open`, `__import__`, `eval`, `exec` of arbitrary modules, `os`, `subprocess`, `socket`),
- a namespace exposing only `df` (the dataframe), `pd` (pandas), and a small set of safe helpers,
- a wall-clock **timeout** per execution,
- no network access encouraged by the namespace and no filesystem-write helpers exposed,
- captured `stdout` as the "intermediate steps".

> **Assumed (risk):** This is a *practical* sandbox, not a hardened security boundary. A determined or adversarial code string could still attempt escapes (Python sandboxing is not airtight). The threat model is "the LLM occasionally writes buggy or overreaching pandas," not "a malicious actor controls the generated code." Run only on a trusted local machine with non-sensitive credentials in the environment. Hardening (subprocess isolation, seccomp, resource limits) is out of v1 scope.

## Stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Language | Python 3.11+ | per baseline `pyproject.toml` `requires-python = ">=3.11"` |
| Agent framework | LangGraph (`langgraph>=0.1`) | code-interpreter loop — see `spec/agent.md` |
| LLM provider | Google Gemini (`google-genai`) | `GeminiProvider`, auto-detected from `AGENT_GEMINI_API_KEY` |
| LLM model | **`gemini-2.5-pro`** (default) | env-overridable via `AGENT_LLM_MODEL`; baseline `GeminiProvider.DEFAULT_MODEL` is already `gemini-2.5-pro`. (Note: `harness/patterns/tech-stack.md` lists `gemini-2.5-flash` as the generic safe default; this build's intake explicitly pins `gemini-2.5-pro`.) |
| Backend | FastAPI + Uvicorn | single-origin; serves API + static frontend at `/app` on port 8001 |
| Database | **Local SQLite** | `sqlite:///./data/agent.db` via SQLAlchemy 2.0; chosen to honor the data-locality hard constraint (nothing leaves the machine) |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | tables created/migrated via `alembic upgrade head` |
| Data analysis | **pandas** (new dep) | parse + profile + execute generated code; add to `[project.dependencies]` in Phase 1 |
| Excel ingest | **openpyxl** (new dep, Phase 2 only) | `pandas.read_excel` engine |
| Frontend | Next.js 15 static export (`output: 'export'`, `basePath: '/app'`) + React, Tailwind v4 | mounted by FastAPI at `/app`; built via `pnpm build` → `frontend/out/` |
| Dependency mgmt | uv (Python) / pnpm (TypeScript) | |
| Observability | structlog (`src/observability/events.py`) | structured JSON logs, carried every phase |
| Config | pydantic-settings, env prefix `AGENT_` | `.env` (gitignored) holds `AGENT_GEMINI_API_KEY`, optional `AGENT_LLM_MODEL`, `AGENT_DATABASE_URL` |

### Package layout (extends the wired baseline in place)

The package lives directly under `src/` (e.g. `src/graph`, `src/api`, `src/llm`, `src/db`, `src/config`), **not** `src/agent/`. The capability slot `transform_text` (`src/graph/nodes.py` + `src/prompts/transform.md` + `frontend/src/app/page.tsx`) is **replaced** by the data-analysis flow. Generators extend the existing wired pieces (graph runner, API app, DB session, settings, LLM client) in place — they do not copy or rename.

New modules added by this build:
- `src/datasets/` — `storage.py`, `profile.py`, `__init__.py`
- `src/execution/` — `sandbox.py`, `__init__.py`
- `src/api/datasets.py`, `src/api/analyses.py`
- `src/domain/dataset.py`, `src/domain/analysis.py`
- `src/prompts/analyze.md` (replaces `transform.md`)
- `frontend/src/app/components/*`
