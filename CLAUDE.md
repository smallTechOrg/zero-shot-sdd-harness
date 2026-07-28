# Claude Code — Entry Point

This is a spec-driven development boilerplate. Read this file first, then follow the instructions below.

## What This Repo Is

A starting template for building projects. The spec in `spec/` is either:
- **Partially or fully filled in** — you are implementing a project from a completed spec
- **Empty / placeholder** — you are in the build phase; run `/zero-shot-build` to drive the spec and build

## Your First Action Every Session

1. Read `harness/rules/ai-agents.md` — mandatory rules for all AI sessions
2. Check whether `spec/roadmap.md` has been filled in:
   - If it still contains `<!-- FILL IN -->` placeholders → the spec is not ready; do not write application code yet
   - If it is filled in → proceed to read the full spec manifest below before touching any code

## Spec Manifest (read in this order when spec is complete)

```
spec/roadmap.md
spec/architecture.md
spec/capabilities/          ← all files
spec/data.md
spec/api.md
spec/ui.md
spec/agent.md     ← N/A for this website (no agent framework)
harness/rules/ai-agents.md
harness/patterns/spec-driven.md
harness/patterns/phases.md
harness/patterns/project-layout.md
harness/patterns/engineering-practices.md
harness/patterns/test-driven.md
harness/patterns/ui-ux.md
harness/patterns/tech-stack.md     ← generic stack rules (chosen stack is in spec/architecture.md)
harness/patterns/code.md           ← generic code conventions
harness/patterns/agentic-ai.md     ← catalogue of agentic patterns (chosen graph is in spec/agent.md)
harness/rules/git.md
```

**`spec/agent.md` is N/A for this project** — this is a luxury real-estate marketing website with no agent orchestration framework (no LangGraph/CrewAI/AutoGen), so no agent-graph spec is required and a missing `spec/agent.md` is not a blocker. (The reusable catalogue of agentic-AI patterns in `harness/patterns/agentic-ai.md` does not apply to this website.)

## If the Spec Is Not Ready

Tell the user to run **`/zero-shot-build [their idea]`**. That skill runs one intake round — the only interactive setup step. It may ask additional clarifying questions, and asks the user to fill `.env` with the required secrets (e.g. `DATABASE_URI`, `PAYLOAD_SECRET`). Once intake completes, the **project-builder** orchestrator runs design → scaffold → build, one phase per invocation. It is autonomous *within* a phase and stops at each phase boundary for a **human testing gate** — the user tests the increment before the next phase starts. Each phase delivers the smallest user-testable win, built first-time-right on the tested path.

## Skills (entry points)

These are the entry points. All are manual (`disable-model-invocation: true`). Each is invocable as a skill **and** as a slash command (`.claude/commands/<name>.md` defers to the skill — the skill is the source of truth, so the two never drift).

| Skill / command | Purpose |
|-----------------|---------|
| `/zero-shot-build [idea]` | Idea → working, verified skeleton (drives the project-builder). Also adds a new capability. |
| `/zero-shot-fix [target]` | Diagnose + fix a bug, error, failing test, or spec/code drift, then verify. |
| `/zero-shot-sync [scope]` | Reconcile spec ↔ code so they match (spec wins), then verify. |

## Key Rules (summary — full rules in harness/rules/ai-agents.md)

- Never write application code before reading the full spec
- Never skip a phase — complete phase N before starting phase N+1
- Commit every logical unit of work; never let the working tree stay dirty
- Each phase is tested by the human before the next phase starts — stop at the phase boundary, hand off the test instructions, and wait for the user
- Tight scope, first-time-right — each phase is the smallest user-testable win and must work the first time the user tests it; zero rough edges on the tested path
- Tests run against the real local Postgres + Payload app (using `.env`) — never gate the build on a mock DB or offline/stubbed runs
- When in doubt, ask at intake — do not guess requirements; once intake completes, build a phase autonomously and stop for the human testing gate

## The skeleton in `src/`

`src/` is the **opinionated baseline** — a working Next.js 16 (App Router) + Payload CMS v3 + Tailwind + Postgres app, with Payload embedded inside the Next app (Payload IS the server). `pnpm dev` boots the site on http://localhost:3000; tests pass out of the box. Generators extend this in place — they never copy or rename. The main slots are:

- `src/app/(frontend)/` — public marketing-site routes (+ `globals.css` design tokens) → build out the pages and sections here
- `src/components/**` — React/Tailwind components → add your UI here
- `src/payload.config.ts` + `src/collections/**` — Payload config and collections → add content models here
- `tailwind.config.ts` + `src/app/(frontend)/globals.css` — design tokens (Tailwind theme + CSS custom properties)

Everything else (`src/app/(payload)` admin + `/api` route groups, `src/lib`, `next.config.mjs` wrapped with `withPayload`, the Postgres adapter via `@payloadcms/db-postgres`, settings, and test fixtures) is already wired and tested — do not change it unless the spec requires it.

## Sub-agents (the team)

`/zero-shot-build` delegates a full build to **project-builder**, which plans and coordinates the rest and owns git/PR. `/zero-shot-fix` and `/zero-shot-sync` call the workers directly (no project-builder) and own git themselves. Each agent is one full, self-contained definition at `.claude/agents/<name>.md` (the path is the agent slug).

| Agent | Role | Tools |
|-------|------|-------|
| project-builder | Orchestrator — plans phases, fans out code-generator instances per slice (in parallel), and owns the git/PR surface for a build | read/bash/agent |
| spec-writer | The single design authority — writes the FULL spec (incl. architecture + phased plan) **and** self-reviews it | read/write |
| code-generator | Implements ONE independent slice (a disjoint directory set within the one Next+Payload app — e.g. UI `src/components`+`src/app/(frontend)`, CMS `src/payload.config.ts`+`src/collections`, or tokens `tailwind.config.ts`+`globals.css`) plus tests — spawned in parallel, one per slice | read/write/bash |
| qa-auditor | Independent review **and** run gates/tests/app **and** audit spec↔code drift; runs FIRST in fix/sync and classifies root cause SPEC-vs-CODE | read-only (bash) |

Pattern: **spec-writer** writes the whole spec and carves each phase into independent slices. **project-builder** fans out one **code-generator** per slice in a single Agent message (max parallelism — disjoint paths, never conflict). **qa-auditor** independently gates each slice and audits drift — it never edits. The **human tests between phases**.
