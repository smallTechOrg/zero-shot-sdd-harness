# Implementation Phases

Projects are built phase by phase, derived from the user's requirements — not a fixed ladder. **Phase 1
is the smallest user-testable win that works first time;** each later phase wires a stub into a real
feature. Production concerns trail behind the requirements. None of this is language- or
framework-specific — the concrete gate commands per phase come from `spec/architecture.md` (`## Stack`).

## Core Principle

**Smallest win first, then complete, then polish.**

Phase 1 is the SMALLEST user-testable win that works the FIRST time the user tests it — real on the one
core path, with clearly-labelled stubs for everything else (this is the same rule the spec-writer
applies; the two must agree). It is fine for Phase 1 to be smaller than "complete" — what matters is that
the one path it delivers is real and impresses, not that it covers every requirement. Later phases wire
the labelled stubs into real features, one human-tested increment at a time. Do NOT over-scope Phase 1 to
cover "all the primary requirements" — that is the over-build that doubles build time and breaks
first-time-right.

The spec-writer derives the phase breakdown from `spec/roadmap.md` — the count and names come from the
requirements, not a fixed ladder.

## Phase Structure

Two roles are always present; the middle phases are derived from requirements:

---

### Phase 1 — First Win

Phase 1 is the **smallest user-testable win** — the full primary user journey end-to-end, real and
working the first time, that the person who briefed the idea immediately appreciates. Not every feature:
the complete primary flow, done right, with supporting features as labelled stubs.

- **Full primary journey, not "all the features."** Deliver the complete end-to-end flow that proves the
  idea — every step the user must take to get a real result. Defer secondary features (export, history,
  multi-item, settings) to later phases as clearly-labelled stubs. Over-scoping Phase 1 to cover every
  feature is the failure mode, not the goal.
- If a capability is itself an AI agent (a tool-use loop, a multi-step graph, a multi-agent system — see
  `spec/agent.md` and `harness/patterns/agentic-ai.md`, both OPTIONAL), its core structure (state, the
  entry node/step, the assembly) is wired from day one even if some capability nodes are stubs. Never
  defer the agentic skeleton once one is chosen. Most projects have no such component at all — skip this
  entirely if `spec/agent.md` doesn't exist.
- Any user-facing surface is visually complete: real UI for the one path Phase 1 delivers, PLUS
  clearly-labelled stubs for what's coming. Stubs are never mistaken for bugs.
- All calls on the tested path hit real dependencies (credentials from `.env` where the project has any
  external provider) — no fake data on what the user tests.
- **Gate (all must pass — the exact commands come from `spec/roadmap.md`, following `spec/architecture.md`'s stack):**
  1. Any database driver is declared as a production dependency, never dev-only
  2. Any pending migration has been run against the configured database and confirmed applied (not
     assumed) — via this stack's verification step (e.g. `alembic current`, `prisma migrate status`)
  3. **Boots via the documented run command** — the app starts on its exact README/roadmap run command
     from the project root, with no import/module-resolution error. A green unit-test run does NOT prove
     this on its own in every ecosystem (some test runners mask import bugs that only surface on the real
     entry point) — the test path must equal the run path.
  4. Primary user journey works end-to-end against real dependencies; tests pass
  5. **If an agentic component exists:** its skeleton compiles/runs, state flows through it, it's
     invocable — confirmed by the Phase 1 test. Skip if no `spec/agent.md`.
  6. **Styled-render (any UI with a build step):** after the build, the served page is rendered AND
     styled — the built output contains real compiled styles and no unexpanded template directives. An
     unstyled 200 fails the gate.
  7. **Automated E2E (any project with a frontend):** a browser-driven smoke suite runs against the live
     app and asserts the primary user journey renders correctly, is interactive, and shows real output —
     not just a 200. A styling check alone is not sufficient.
  8. **Observability wired, where the project has an agentic or LLM-calling component:** tracing and/or
     structured request/response logging confirmed working — a log line or trace appears for the Phase 1
     end-to-end run. For projects with no such component, ordinary structured logging of key operations
     is the equivalent bar.
  9. Working tree is clean and committed
  10. Phase test-handoff published; the human has tested and approved (see Human Testing Gate)

---

### Phases 2–N — Requirements Phases *(spec-writer derives these)*

Each phase covers a chunk of remaining user requirements from `spec/roadmap.md`. The spec-writer **names
these phases after what they deliver**, not after generic production concerns. Aim for all user
requirements covered by phase 2–3 — fewer, bigger phases beat many thin ones.

- Each phase wires Phase-1 stubs into real functionality — a **minimum of 3 capabilities per phase**.
  Never deliver a single capability in isolation; group related capabilities that form a coherent user
  story and build them together. A phase with fewer than 3 capabilities is too thin — collapse it into
  the adjacent phase.
- All external calls hit real dependencies using credentials from `.env`; tests assert on real responses
  (shape/content), not hardcoded strings.
- **Gate:** The phase's user-testable increment works end-to-end against real dependencies; tests pass;
  working tree clean; human approved.

---

### Optional Phase — Agentic Architecture Upgrade *(only if `spec/agent.md` exists AND calls for patterns beyond the base loop)*

If a project has an agentic component and its spec's agent graph needs more than a base tool-use loop, add
a phase to upgrade the architecture and harden external calls. A simple single-loop agent that already
meets its requirements does not need this phase — do not add it by default, and most projects never have
this phase at all.

- **Upgrade the agentic stack** per `spec/agent.md`: wire in the patterns it calls for beyond the base
  loop — planning, reflection, multi-agent coordination, memory, or whatever the spec requires.
- Add error handling to all external calls: retries, timeouts, graceful degradation on non-critical
  failures.
- **Gate:** every pattern listed in `spec/agent.md` beyond the base loop is wired and exercised by a real
  test; the agent handles all documented failure modes without crashing.

---

### The Final Requirements Phase — every capability real

The last phase turns any remaining labelled stubs into real features so every capability in
`spec/roadmap.md` is active and the system runs fully end-to-end.

- Every capability in `spec/roadmap.md` is real — no stubs on any active path.
- Complete any remaining integrations; system runs against all real dependencies.
- **Gate:** all integrations are real and the system runs fully end-to-end; every capability in the spec
  is implemented and tested with real data; if `spec/agent.md` exists, its graph matches the running code
  (drift audit passes on the agentic surfaces).

---

### Trailing Phases *(only if the spec requires them)*

These phases exist only when the spec explicitly calls for them — never as defaults:

- **API / CLI Surface** — only if `spec/api.md` calls for an external API or CLI
- **UI Polish** — only if `spec/ui.md` calls for further UI work beyond Phase 1
- **Advanced Observability** — dashboards, metrics, alerting beyond the basic tracing/logging already
  wired in Phase 1
- **Polish + Hand-off** — final drift audit; README verified end-to-end from a clean clone; user accepts
  hand-off

---

## Human Testing Gate

The build is autonomous WITHIN a phase, with a human testing gate BETWEEN phases — at EVERY phase
boundary.

After a phase passes its automated gate and is committed, the build publishes a **test-handoff** and
STOPS:
- The handoff gives exact run commands, what to click/look at, the expected result, and what is a
  labelled stub vs. real.
- Only the root session presents it and asks the human.
- The next phase starts ONLY after the human approves.
- On a reported issue → qa-auditor diagnoses and routes → the responsible generator fixes → re-gate →
  re-present.

## Parallel Slices Within a Phase

- spec-writer carves each phase into INDEPENDENT SLICES (the parallel units) with explicit dependencies;
  default to independence so slices build concurrently.
- agent-builder fans out a generator per slice — multiple code-generator invocations in a SINGLE message
  so they run concurrently (disjoint paths per this project's actual surfaces, e.g. frontend vs. backend,
  or service A vs. service B — never the same file from two generators). Then fans out qa-auditor per
  slice concurrently and aggregates verdicts.
- Serialize ONLY across a true declared dependency. On a BLOCKED slice, loop only that slice's generator;
  other slices are unaffected. For a headless/CLI-only project, only backend-shaped generators run.

## Phase Gates

A phase is complete when ALL of the following are true:
1. All code for the phase is committed and pushed
2. All tests for the phase pass
3. Working tree is clean
4. Phase test-handoff published; (build) human tested and approved
5. qa-auditor sub-agent (or manual QA checklist) has signed off
6. For Phase 1 specifically, if the project has a database: its migration has been run against the real
   DB and succeeded
7. **README updated** — every command, env var, setup step, route, or capability this phase added is
   reflected in `README.md`, and every README command in scope has been run and confirmed to work from the
   stated directory. A stale README is a BLOCKER.

**Never mark a phase complete if any gate is red.**

**Never claim a phase passes based on tests alone if those tests used a different database engine than
production.** A lightweight-substitute test suite passing does not mean the real migrations and queries
work.

**Never claim a phase with external dependencies passes on stubbed providers** — the gate runs against
the real dependency with credentials from `.env`.

## Phase Tracking

The current phase is recorded in git commit messages (`phase-N: [description]`). To see phase history,
run `git log --oneline | grep "phase-"`.

## Adapting the Phases

The spec-writer derives the phases from `spec/roadmap.md`. What is fixed:

- **Phase 1 is always the smallest user-testable win** — the one core path real and first-time-right, the
  rest as labelled stubs (this matches `spec-writer.md` exactly; the two never disagree)
- **If the project has an agentic component, its skeleton is wired in Phase 1** — never deferred; if it
  doesn't have one, this simply doesn't apply
- **An Agentic Architecture Upgrade phase is added only when `spec/agent.md` exists and calls for
  patterns beyond the base loop** — a simple agent that meets its requirements does not get one by
  default, and most projects have none at all
- **Trailing phases are only added when the spec explicitly requires them**

What varies (derived from requirements):
- How many requirements phases (2–N) — count comes from `spec/roadmap.md`; target 1–2 requirements
  phases. Each must contain at least 3 capabilities — if a phase would have fewer, collapse it into the
  adjacent one.
- Names of requirements phases — named after what they deliver (e.g. "Profiling + Charts + Export",
  "History + Multi-file + Settings"), not generic concerns.

---

## Gate Commands Are Project-Specific

The spec-writer sets the exact gate command per phase in `spec/roadmap.md` (`## Phases of Development`),
honoring the test rules in `harness/patterns/tech-stack.md`, and using whatever this project's actual
stack's tooling is (its test runner, its migration tool, its package manager). This file intentionally
does not hardcode a per-language table — hardcoding one here is exactly the kind of assumption this
harness generalizes away from. Record the real commands once, in `spec/architecture.md` and
`spec/roadmap.md`, and every gate references them from there.
