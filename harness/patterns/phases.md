# Implementation Phases

Agents are built incrementally. This file defines the default phase model. The spec-writer sub-agent adapts it to your specific project.

## Core Principle

**Ship the smallest user-testable win first. Then expand.**

Phase 1 is a thin but REAL vertical slice the user can test the first time, with zero rough edges on the tested path — never a models-only layer the user cannot exercise. Backend on the one core path is minimal but real (no fake data on the tested path); the frontend, built in parallel, is visually complete: real UI for the working path PLUS clearly-labelled non-functional stubs for everything coming later, so the user sees the vision. Each subsequent phase wires a stub into real functionality — one user-testable increment at a time.

## Default Phase Model

The spec-writer sub-agent will customize this for your project, but the general structure is:

### Phase 1 — Smallest User-Testable Win (thin real vertical slice)
- One core path works end-to-end against the real LLM/API (keys from `.env`): the minimal domain types, data layer, and core logic that path needs — nothing more.
- Backend is minimal but REAL on that path — no fake data on what the user tests.
- Frontend (built in parallel) is visually complete: real UI for the one working path, PLUS clearly-labelled non-functional stubs for everything coming later. A stub must be visibly labelled so it is never mistaken for a bug.
- **Gate (all must pass):**
  1. `pyproject.toml` declares the DB driver in `[project.dependencies]` (e.g. `psycopg2-binary` for PostgreSQL) — never dev-only
  2. `uv run alembic upgrade head` succeeds against the configured database — this must be run and confirmed, not assumed
  3. The core path runs end-to-end against the real LLM/API; tests for the slice pass
  4. Working tree is clean and committed
  5. Phase test-handoff published; the human has tested the slice and approved (see Human Testing Gate)

### Phase 2 — Core Agent Loop (Real Integration)
- Implement the agent's main loop from start to finish.
- All external calls hit the real provider (LLM/API/search) using keys loaded from `.env`.
- The agent runs end-to-end against the real LLM; tests assert on real responses (shape/content), not hardcoded strings.
- A stub provider MAY remain as an optional fallback for offline development, but it is not required and tests are NOT expected to pass with keys unset.
- **Gate (all must pass):**
  1. Agent runs end-to-end; at least one record written to DB; run status "completed"
  2. `pytest` passes against the **production DB driver** (e.g. PostgreSQL via psycopg2, not SQLite) **with** real LLM/API keys loaded from `.env`
  3. Tests are fully automated: `conftest.py` creates and tears down the test schema; no manual DB setup steps
  4. Real LLM/API keys are present in `.env` and the suite exercises the real provider — no all-stubbed run is accepted as the Phase 2 gate
  5. **Golden-path UI smoke test passes** (if the project has any UI or HTTP surface). Drives the full primary user flow through `TestClient` against the real LLM/API and asserts real response content (not only status codes). Edge-case and end-to-end UI assertions are required, not optional.
  6. **Live-server smoke:** the agent starts the app (`uv run python -m <pkg>`) and hits `/health` plus one real page with `curl`, exercising the live LLM/API path. Both return 200 and the page shows real AI output.

### Phase 3 — Remaining Integrations
- Wire up any secondary providers or data sources not covered by the Phase 2 core loop.
- **Gate:** Each integration runs for real; happy path works end-to-end with real data.

### Phase 4 — Error Handling + Resilience
- Add try/catch, retries, timeouts to all external calls
- Agent should continue (degraded, not crashed) on non-critical failures
- **Gate:** Agent handles all documented failure modes without crashing

### Phase 5 — Full Integration Pass
- Complete any remaining secondary integrations and verify the whole system runs against real services.
- **Gate:** All integrations are real; agent runs fully end-to-end

### Phase 6 — API / CLI Surface
- Add the external API or CLI (if the spec calls for it)
- **Gate:** All specified endpoints/commands work correctly

### Phase 7 — Basic UI (if required)
- Implement the UI from `spec/ui.md`
- Functional but not polished
- **Gate:** All specified screens/views are present and functional

### Phase 8 — Integration Tests
- Write integration tests that exercise the full system against real services, including edge cases, error paths, and any UI journey.
- **Gate:** Integration, edge-case, end-to-end, and UI tests pass reliably against the real LLM/API

### Phase 9 — Observability + Logging
- Add structured logging, metrics, and monitoring
- **Gate:** Every major operation produces a log entry; errors are surfaced

### Phase 10 — Polish + Hand-off
- Fix rough edges, improve error messages, update docs
- Final drift audit: code matches spec
- README is accurate and up to date
- **Gate:** Drift audit passes; README reviewed by user; user accepts hand-off

## Human Testing Gate

The build is autonomous WITHIN a phase, with a human testing gate BETWEEN phases — at EVERY phase boundary.

After a phase passes its automated gate and is committed, the build publishes a **test-handoff** and STOPS:
- The handoff gives exact run commands, what to click/look at, the expected result, and what is a labelled stub vs. real.
- Only the root session presents it and asks the human.
- The next phase starts ONLY after the human approves.
- On a reported issue → qa-auditor diagnoses and routes → the right generator (frontend and/or backend) fixes → re-gate → re-present.

## Parallel Slices Within a Phase

- spec-writer carves each phase into INDEPENDENT SLICES (the parallel units) with explicit dependencies; default to independence so slices build concurrently.
- agent-builder fans out a generator per slice — multiple backend-code-generator AND frontend-code-generator invocations in a SINGLE message so they run concurrently (disjoint paths: frontend writes the frontend surface, backend writes `src/` — never the same file). Then fans out qa-auditor per slice concurrently and aggregates verdicts.
- Serialize ONLY across a true declared dependency. On a BLOCKED slice, loop only that slice's generator; other slices are unaffected. For headless/CLI builds, only backend generators run.

## Phase Gates

A phase is complete when ALL of the following are true:
1. All code for the phase is committed and pushed
2. All tests for the phase pass
3. Working tree is clean
4. Phase test-handoff published; (build) human tested and approved
5. qa-auditor sub-agent (or manual QA checklist) has signed off
6. For Phase 1 specifically: `alembic upgrade head` has been run against the real DB and succeeded

**Never mark a phase complete if any gate is red.**

**Never claim a phase passes based on tests alone if those tests use a different DB driver than production.** SQLite tests passing does not mean PostgreSQL migrations work.

**Never claim Phase 2+ passes on stubbed providers** — the gate runs against the real LLM/API with keys from `.env`.

## Phase Tracking

The current phase is recorded in git commit messages (`phase-N: [description]`). To see phase history, run `git log --oneline | grep "phase-"`.

## Adapting the Phases

The spec-writer sub-agent may merge, split, or reorder phases based on your project's specifics. For example:
- A pure CLI tool may skip phases 6 and 7
- A project with no database may shrink phase 1
- A project with many integrations may split phase 5 into multiple phases

Whatever the spec-writer decides, the core principle holds: **smallest user-testable win first**.

---

## Language-Specific Gate Commands

The gate test command depends on the project language. The spec-writer sets the exact command per phase in `spec/roadmap.md` (## Phases of Development), honoring the test rules in `harness/patterns/tech-stack.md`.

| Language | Phase 1 gate | Phase 2 gate |
|----------|-------------|-------------|
| Python | `uv run alembic upgrade head` + `uv run pytest` | `uv run pytest` (PostgreSQL, automated via conftest) |
| TypeScript (Bun) | migration tool + `bun test tests/unit/` | `bun test tests/integration/` |
| TypeScript (Node) | migration tool + `npx vitest run tests/unit/` | `npx vitest run tests/integration/` |
| Go | `migrate up` + `go test ./internal/...` | `go test ./...` |

The Phase 2 gate runs with **real LLM/API keys loaded from `.env`** regardless of language; both the DB URL and the provider key(s) must be set.

## TypeScript/Bun Phase 2 Test Pattern

```typescript
// tests/integration/pipeline.test.ts
import { describe, it, expect, beforeEach } from "bun:test";

// Use the production DB driver via conftest-style setup/teardown — never SQLite-as-a-substitute
// Call the real LLM/API using keys from .env

describe("pipeline", () => {
  it("runs end-to-end against the real provider", async () => {
    // call runner against the real provider
    // assert DB record created with correct status
  });
});
```
