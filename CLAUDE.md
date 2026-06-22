# Claude Code — Entry Point

This is a spec-driven AI agent boilerplate. Read this file first, then follow the instructions below.

## What This Repo Is

A starting template for building AI agents. The spec in `spec/` is either:
- **Partially or fully filled in** — you are implementing an agent from a completed spec
- **Empty / placeholder** — you are in the build phase; run `/zero-shot-build` to drive the spec and build

## Your First Action Every Session

1. Read `harness/rules/ai-agents.md` — mandatory rules for all AI sessions
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
spec/agentic-ai.md      ← REQUIRED for any agent framework project
harness/rules/ai-agents.md
harness/patterns/spec-driven.md
harness/patterns/phases.md
harness/patterns/project-layout.md
harness/patterns/engineering-practices.md
harness/patterns/test-driven.md
harness/patterns/ui-ux.md
harness/rules/git.md
spec/tech-stack.md
spec/code-style.md
```

**`agentic-ai.md` is mandatory** for any project using LangGraph, CrewAI, AutoGen, or any agent orchestration framework. If it does not exist when you reach Phase 2, stop and raise it as a blocker.

## If the Spec Is Not Ready

Tell the user to run **`/zero-shot-build [their idea]`**. That skill runs one intake round and a single approval, then hands the build to the **agent-builder** orchestrator, which coordinates the team to a verified skeleton autonomously.

## Skills (entry points)

These are the entry points. All are manual (`disable-model-invocation: true`). Each is invocable as a skill **and** as a slash command (`.claude/commands/<name>.md` defers to the skill — the skill is the source of truth, so the two never drift).

| Skill / command | Purpose |
|-----------------|---------|
| `/zero-shot-build [idea]` | Idea → working, verified skeleton (drives the agent-builder). Also adds a new capability. |
| `/zero-shot-fix [target]` | Diagnose + fix a bug, error, failing test, or spec/code drift, then verify. |
| `/zero-shot-sync [scope]` | Reconcile spec ↔ code so they match (spec wins), then verify. |

## Key Rules (summary — full rules in harness/rules/ai-agents.md)

- Never write application code before reading the full spec
- Never skip a phase — complete phase N before starting phase N+1
- Commit every logical unit of work; never let the working tree stay dirty
- Update `reports/sessions/` at the start and end of every session
- When in doubt, ask — do not guess requirements

## Sub-agents (the team)

`/zero-shot-build` delegates a full build to **agent-builder**, which coordinates the rest. `/zero-shot-fix` and `/zero-shot-sync` call the workers directly (no agent-builder). Makers are paired with independent checkers.

**Each agent is defined twice:** a thin registry stub at `.claude/agents/<name>.md` (frontmatter the Agent tool needs + a pointer) and its **detailed, canonical definition** at `harness/agents/<name>.md`. The stub is what gets invoked; the harness file is the source of truth for behaviour — edit there. See `harness/agents/README.md` for the index.

| Agent | Detailed definition | Role | Tools |
|-------|---------------------|------|-------|
| agent-builder | `harness/agents/agent-builder.md` | Orchestrator — coordinates the team for a full build | read/bash/agent |
| spec-writer | `harness/agents/spec-writer.md` | Write the product spec | read/write |
| spec-reviewer | `harness/agents/spec-reviewer.md` | Independent spec review | read-only |
| tech-architect | `harness/agents/tech-architect.md` | Design **and** review stack/architecture/agentic-ai/plan | read/write |
| code-generator | `harness/agents/code-generator.md` | Write code + tests for one phase / one fix | read/write/bash |
| code-reviewer | `harness/agents/code-reviewer.md` | Independent code review (logic, security, spec-fidelity) | read-only |
| qa-auditor | `harness/agents/qa-auditor.md` | Run gates/tests/app **and** audit spec↔code drift | read-only (bash) |
| deployer | `harness/agents/deployer.md` | Branch, commit, push, PR — owns the git surface | read-only (bash) |

Pattern: maker → checker. spec-writer↔spec-reviewer, code-generator↔code-reviewer; tech-architect is a combined design+review role; qa-auditor runs (it never edits); deployer owns version control.
