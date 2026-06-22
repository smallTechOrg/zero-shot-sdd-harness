# Claude Code — Entry Point

This is a spec-driven AI agent boilerplate. Read this file first, then follow the instructions below.

## What This Repo Is

A starting template for building AI agents. The spec in `spec/` is either:
- **Partially or fully filled in** — you are implementing an agent from a completed spec
- **Empty / placeholder** — you are in the build phase; invoke the agent-builder to fill the spec first

## Your First Action Every Session

1. Read `harness/ai-agents.md` — mandatory rules for all AI sessions
2. Check whether `spec/01-vision.md` has been filled in:
   - If it still contains `<!-- FILL IN -->` placeholders → the spec is not ready; do not write application code yet
   - If it is filled in → proceed to read the full spec manifest below before touching any code
3. Open a session report at `reports/sessions/YYYY-MM-DD-HHMMSS-[branch].md`

## Spec Manifest (read in this order when spec is complete)

```
spec/01-vision.md
spec/02-architecture.md
spec/capabilities/          ← all files
spec/04-data-model.md
spec/05-api.md
spec/06-ui.md
spec/07-agent-graph.md      ← REQUIRED for any agent framework project
harness/ai-agents.md
harness/spec-driven.md
harness/phases.md
harness/project-layout.md
spec/tech-stack.md
spec/code-style.md
```

**`07-agent-graph.md` is mandatory** for any project using LangGraph, CrewAI, AutoGen, or any agent orchestration framework. If it does not exist when you reach Phase 2, stop and raise it as a blocker.

## If the Spec Is Not Ready

Invoke the agent-builder:

```
Use the agent-builder sub-agent in .claude/agents/agent-builder.md
```

Or the user can run the `/build` command with their idea.

## Key Rules (summary — full rules in harness/ai-agents.md)

- Never write application code before reading the full spec
- Never skip a phase — complete phase N before starting phase N+1
- Commit every logical unit of work; never let the working tree stay dirty
- Update `reports/sessions/` at the start and end of every session
- When in doubt, ask — do not guess requirements

## Sub-agents Available

| Agent | Purpose |
|-------|---------|
| `.claude/agents/agent-builder.md` | Master orchestrator — start here for a new build |
| `.claude/agents/spec-writer.md` | Interview user, write product spec |
| `.claude/agents/spec-reviewer.md` | Review spec for completeness and coherence |
| `.claude/agents/tech-designer.md` | Propose tech stack and architecture |
| `.claude/agents/planner.md` | Create phased implementation plan |
| `.claude/agents/plan-reviewer.md` | Validate plan against spec |
| `.claude/agents/drift-auditor.md` | Audit spec/code drift |
| `.claude/agents/qa-auditor.md` | Test and audit completed phases |
