# Claude Code — Entry Point

This is a spec-driven AI agent boilerplate. Read this file first, then follow the instructions below.

## What This Repo Is

A starting template for building AI agents. The spec in `spec/` is either:
- **Partially or fully filled in** — you are implementing an agent from a completed spec
- **Empty / placeholder** — you are in the build phase; run `/zero-shot-build` to drive the spec and build

## Your First Action Every Session

1. Read `harness/ai-agents.md` — mandatory rules for all AI sessions
2. Check whether `spec/vision.md` has been filled in:
   - If it still contains `<!-- FILL IN -->` placeholders → the spec is not ready; do not write application code yet
   - If it is filled in → proceed to read the full spec manifest below before touching any code
3. Open a session report at `reports/sessions/YYYY-MM-DD-HHMMSS-[branch].md`

## Spec Manifest (read in this order when spec is complete)

```
spec/vision.md
spec/architecture.md
spec/capabilities/          ← all files
spec/data-model.md
spec/api.md
spec/ui.md
spec/agent-graph.md      ← REQUIRED for any agent framework project
harness/ai-agents.md
harness/spec-driven.md
harness/phases.md
harness/project-layout.md
spec/tech-stack.md
spec/code-style.md
```

**`agent-graph.md` is mandatory** for any project using LangGraph, CrewAI, AutoGen, or any agent orchestration framework. If it does not exist when you reach Phase 2, stop and raise it as a blocker.

## If the Spec Is Not Ready

Tell the user to run **`/zero-shot-build [their idea]`**. That skill is the orchestrator: it runs one intake round, drafts the spec/tech/plan, gets a single approval, then builds and verifies autonomously.

## Skills (entry points)

These are the only entry points. All are manual (`disable-model-invocation: true`) — invoke with `/<name>`.

| Skill | Purpose |
|-------|---------|
| `/zero-shot-build [idea]` | Idea → working, verified skeleton. Also adds a new capability to an existing spec. |
| `/zero-shot-fix [target]` | Diagnose + fix a bug, error, failing test, or spec/code drift, then verify. |
| `/zero-shot-sync [scope]` | Reconcile spec ↔ code so they match (spec wins), then verify. |

## Key Rules (summary — full rules in harness/ai-agents.md)

- Never write application code before reading the full spec
- Never skip a phase — complete phase N before starting phase N+1
- Commit every logical unit of work; never let the working tree stay dirty
- Update `reports/sessions/` at the start and end of every session
- When in doubt, ask — do not guess requirements

## Sub-agents (workers the skills drive directly)

| Agent | Role | Tools |
|-------|------|-------|
| `.claude/agents/spec-author.md` | Draft + self-review the product spec | read/write |
| `.claude/agents/tech-designer.md` | Decide stack, fill tech-stack/code-style/agent-graph | read/write |
| `.claude/agents/planner.md` | Phased implementation plan with gate tests | read/write |
| `.claude/agents/implementer.md` | Write code + tests for one phase / one fix | read/write/bash |
| `.claude/agents/auditor.md` | Read-only spec↔code drift verdict | read-only |
| `.claude/agents/verifier.md` | Read-only: run gates/app, return pass/fail | read-only (bash) |

There is no master orchestrator agent — the skill body is the orchestrator. The spec-author and planner self-review; the verifier gates each phase; the auditor is the final drift check.
