# Implementation Phases

Projects are built phase by phase, derived from the user's requirements — not a fixed ladder. **Phase 1 is the smallest user-testable win that works first time;** each later phase wires a stub into a real feature. Production concerns trail behind the requirements.

## Core Principle

**Smallest win first, then complete, then polish.**

Phase 1 is the SMALLEST user-testable win that works the FIRST time the user tests it — real on the one core path, with clearly-labelled stubs for everything else (this is the same rule the spec-writer applies; the two must agree). It is fine for Phase 1 to be smaller than "complete" — what matters is that the one path it delivers is real and impresses, not that it covers every requirement. Later phases wire the labelled stubs into real features, one human-tested increment at a time. Do NOT over-scope Phase 1 to cover "all the primary requirements" — that is the over-build that doubles build time and breaks first-time-right.

The spec-writer derives the phase breakdown from `spec/roadmap.md` — the count and names come from the requirements, not a fixed ladder.

## Phase Structure

Four roles are always present; the middle phases are derived from requirements:

---

### Phase 1 — First Win

Phase 1 is the **smallest user-testable win** — the full primary user journey end-to-end, real and working the first time, that the person who briefed the idea immediately appreciates. Not every feature: the complete primary flow, done right, with supporting features as labelled stubs.

- **Full primary journey, not "all the features."** Deliver the complete end-to-end flow that proves the idea (e.g. upload → profile → ask → answer-with-chart) — every step the user must take to get a real result. Defer secondary features (export, history, multi-file, settings) to later phases as clearly-labelled stubs. Over-scoping Phase 1 to cover every feature is the failure mode, not the goal.
- **The Next + Tailwind foundation is established from day one.** The Next.js App Router app and the Tailwind token layer are scaffolded in Phase 1. Payload CMS + the Postgres connection are introduced when the roadmap's CMS phase calls for them — for Silverwave that is **Phase 3**, per the fixed PR order (design tokens → component library → CMS integration → homepage). Do NOT front-load Payload or a database into a pure-frontend phase. Never defer the app foundation itself.
- Frontend is visually complete: real UI for the one path Phase 1 delivers, PLUS clearly-labelled stubs for what's coming. Stubs are never mistaken for bugs.
- When the tested path has a backend, all its calls hit the real backend — the Payload API and Postgres, config from `.env` — no fake data on what the user tests. A pure-frontend phase (design tokens, component library) has no backend to hit and requires no database.
- **Gate (all must pass):**
  1. `package.json` declares `@payloadcms/db-postgres` in `dependencies` (a real runtime dep) — never dev-only
  2. Payload dev schema push / `pnpm payload migrate` succeeds against the configured Postgres — run and confirmed, not assumed — but ONLY when the phase introduces or changes collections; a pure-frontend phase (e.g. design tokens) has no DB step
  3. **Boots via the documented run command** — the app starts on its exact README/roadmap run command from the project root (`pnpm dev`, or `pnpm build && pnpm start`) and serves `GET http://localhost:3000/` => 200 with no build/module-resolution errors. A green `pnpm test` (vitest) alone does NOT prove the boot path; the test path must equal the run path.
  4. Primary user journey works end-to-end against the real Payload API + Postgres; tests pass
  5. **Styled-render (any UI phase):** after `pnpm build`, the page served by Next at `GET http://localhost:3000/` is rendered AND styled — the built CSS bundle contains real utility selectors and no unexpanded `@tailwind` remains. An unstyled 200 fails the gate.
  6. **Headless E2E (any project with a frontend):** Playwright smoke runs against the live app (`http://localhost:3000/`) and asserts the primary user journey renders correctly, is interactive, and shows real output — not just a 200. A CSS-grep pass without a Playwright pass is not sufficient.
  7. **Observability wired:** structured Next/Payload request/response logging to stdout confirmed working — a log line appears for the Phase 1 end-to-end run. Observability is never deferred.
  8. Working tree is clean and committed
  9. Phase test-handoff published; the human has tested and approved (see Human Testing Gate)

---

### Phases 2–N — Requirements Phases *(spec-writer derives these)*

Each phase covers a chunk of remaining user requirements from `spec/roadmap.md`. The spec-writer **names these phases after what they deliver**, not after generic production concerns. Aim for all user requirements covered by phase 2–3 — fewer, bigger phases beat many thin ones.

- Each phase wires Phase-1 stubs into real functionality — a **minimum of 3 capabilities per phase**. Never deliver a single capability in isolation; group related capabilities that form a coherent user story and build them together. A phase with fewer than 3 capabilities is too thin — collapse it into the adjacent phase.
- All external calls hit the real services (Payload API + Postgres, and any configured integrations) using config from `.env`; tests assert on real responses (shape/content), not hardcoded strings.
- **Gate:** The phase's user-testable increment works end-to-end against the real Payload API + Postgres; tests pass; working tree clean; human approved.

---

### Phase N+1 — Resilience + Hardening *(only if the spec calls for hardening beyond the base app)*

If the spec calls for more than the base request/response path — external integrations, media storage (GCS), form handling, rate limiting — add a phase to harden those surfaces. A site that already meets its requirements on the base path does not need this phase — do not add it by default.

- **Harden external calls** per the spec: add error handling to every external call (media storage, third-party APIs, form submissions) — try/catch, retries, timeouts. The app continues (degraded, not crashed) on non-critical failures.
- **Gate (all must pass):**
  1. Every hardening requirement the spec lists beyond the base path is wired and exercised by a real test
  2. The app handles all documented failure modes without crashing

---

### Phase N+2 — Complete System *(the final requirements phase — every capability real)*

The last phase turns the remaining labelled stubs into real features so every capability in `spec/roadmap.md` is active and the site runs fully end-to-end.

- Every capability in `spec/roadmap.md` is real — no stubs on any active path.
- Complete any remaining integrations; the site runs against all real services (Payload + Postgres + configured storage).
- **Gate (all must pass):**
  1. All integrations are real; the site runs fully end-to-end against the real Payload API + Postgres
  2. Every capability in the spec is implemented and tested with real data
  3. `spec/roadmap.md` matches the running code — drift audit passes

---

### Trailing Phases *(only if the spec requires them)*

These phases exist only when the spec explicitly calls for them — never as defaults:

- **API / CLI Surface** — only if `spec/api.md` calls for an external API or CLI
- **UI Polish** — only if `spec/ui.md` calls for further UI work beyond Phase 1
- **Advanced Observability** — dashboards, metrics, alerting beyond the basic structured Next/Payload logging already wired in Phase 1
- **Polish + Hand-off** — final drift audit; README verified end-to-end from a clean clone; user accepts hand-off

---

## Human Testing Gate

The build is autonomous WITHIN a phase, with a human testing gate BETWEEN phases — at EVERY phase boundary.

After a phase passes its automated gate and is committed, the build publishes a **test-handoff** and STOPS:
- The handoff gives exact run commands, what to click/look at, the expected result, and what is a labelled stub vs. real.
- Only the root session presents it and asks the human.
- The next phase starts ONLY after the human approves.
- On a reported issue → qa-auditor diagnoses and routes → the right generator (frontend and/or backend) fixes → re-gate → re-present.

## Parallel Slices Within a Phase

- spec-writer carves each phase into INDEPENDENT SLICES (the parallel units) with explicit dependencies; default to independence so slices build concurrently.
- project-builder fans out a generator per slice — multiple code-generator invocations in a SINGLE message so they run concurrently (disjoint paths: frontend writes the frontend surface, backend writes `src/` — never the same file). Then fans out qa-auditor per slice concurrently and aggregates verdicts.
- Serialize ONLY across a true declared dependency. On a BLOCKED slice, loop only that slice's generator; other slices are unaffected. For headless/CLI builds, only backend generators run.

## Phase Gates

A phase is complete when ALL of the following are true:
1. All code for the phase is committed and pushed
2. All tests for the phase pass
3. Working tree is clean
4. Phase test-handoff published; (build) human tested and approved
5. qa-auditor sub-agent (or manual QA checklist) has signed off
6. If the phase introduces or changes collections: Payload schema push / `pnpm payload migrate` has been run against the real Postgres and succeeded (a pure-frontend phase like design tokens has no DB step)
7. **README updated** — every command, env var, setup step, route, or capability this phase added is reflected in `README.md`, and every README command in scope has been run and confirmed to work from the stated directory. A stale README is a BLOCKER.

**Never mark a phase complete if any gate is red.**

**Never claim a phase passes based on tests alone if those tests use a different DB driver than production.** SQLite tests passing does not mean PostgreSQL migrations work.

**Never claim Phase 2+ passes on stubbed services** — the gate runs against the real Payload API + Postgres with config from `.env`.

## Phase Tracking

The current phase is recorded in git commit messages (`phase-N: [description]`). To see phase history, run `git log --oneline | grep "phase-"`.

## Adapting the Phases

The spec-writer derives the phases from `spec/roadmap.md`. What is fixed:

- **Phase 1 is always the smallest user-testable win** — the one core path real and first-time-right, the rest as labelled stubs (this matches `spec-writer.md` exactly; the two never disagree)
- **The Next.js + Tailwind foundation is always wired in Phase 1** — the App Router app and the Tailwind token layer; never deferred. Payload CMS + the Postgres connection are introduced at the roadmap's CMS phase (Silverwave: **Phase 3**), not front-loaded into a pure-frontend phase
- **A Resilience + Hardening phase and a Complete System phase are added only when the spec calls for work beyond the base app** — a site that meets its requirements on the base path does not get them by default
- **Trailing phases are only added when the spec explicitly requires them**

What varies (derived from requirements):
- How many requirements phases (2–N) — count comes from `spec/roadmap.md`; target 1–2 requirements phases. Each must contain at least 3 capabilities — if a phase would have fewer, collapse it into the adjacent one.
- Names of requirements phases — named after what they deliver (e.g. "Profiling + Charts + Export", "History + Multi-file + Settings"), not generic concerns

---

## Language-Specific Gate Commands

The spec-writer sets the exact gate command per phase in `spec/roadmap.md` (## Phases of Development), honoring the test rules in `harness/patterns/tech-stack.md`.

| Language | Phase 1 gate | Phase 2+ gate |
|----------|-------------|-------------|
| Next+Payload | `pnpm payload migrate` (only if collections changed) + `pnpm build` | `pnpm test` (vitest) + `pnpm exec playwright test` — against real local Postgres + Payload |
| TypeScript (Bun) | migration tool + `bun test tests/unit/` | `bun test tests/integration/` |
| TypeScript (Node) | migration tool + `npx vitest run tests/unit/` | `npx vitest run tests/integration/` |
| Go | `migrate up` + `go test ./internal/...` | `go test ./...` |

Phase 2+ gates run against the **real local Postgres and Payload app (config loaded from `.env`)** regardless of language; `DATABASE_URI` and any integration config must be set.

## Vitest + Payload Integration Test Pattern

```typescript
// tests/integration/pages.test.ts
import { describe, it, expect, beforeAll } from "vitest";
import { getPayload } from "payload";
import config from "@/payload.config";

// Use the production DB driver (real local Postgres) — never a mock DB or SQLite-as-a-substitute
// Exercise the real Payload local API against the configured database

describe("pages", () => {
  it("creates and reads a record end-to-end against the real DB", async () => {
    const payload = await getPayload({ config });
    // create + query via the Payload local API
    // assert the record exists with the correct status
  });
});
```
