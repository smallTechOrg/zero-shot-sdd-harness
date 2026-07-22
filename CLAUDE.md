# Claude Code — Entry Point

This repo follows a spec-driven development (SDD) harness. It works for **any language, framework, or
project type** — a web app, a CLI, a library, an AI agent, an API service. Read this file first.

## What This Repo Is

A spec-first engineering harness. The spec in `spec/` is either:
- **Partially or fully filled in** — you are implementing against a completed spec
- **Empty / placeholder** — run `/zero-shot-build` to drive the spec and build

Nothing in `harness/` or `spec/` hardcodes a language, framework, or runtime. The project's actual stack
(language, frameworks, database, hosting, key libraries) is recorded once, in `spec/architecture.md`
under `## Stack` — every generic rule in `harness/` refers back to that section rather than assuming
Python, Node, Go, or anything else.

## Your First Action Every Session

1. Read `harness/rules/ai-agents.md` — mandatory rules for all AI sessions
2. Check whether `spec/roadmap.md` has been filled in:
   - If it still contains `<!-- FILL IN -->` placeholders → the spec is not ready; do not write application code yet
   - If it is filled in → proceed to read the full spec manifest below before touching any code

## Spec Manifest (read in this order when spec is complete)

```
spec/roadmap.md
spec/architecture.md              ← includes ## Stack — the concrete language/framework/tools for THIS project
spec/capabilities/                ← all files
spec/data.md
spec/api.md
spec/ui.md
spec/agent.md                     ← OPTIONAL — only if this project has an AI-agent / LLM-orchestration component
harness/rules/ai-agents.md
harness/patterns/spec-driven.md
harness/patterns/phases.md
harness/patterns/project-layout.md
harness/patterns/engineering-practices.md
harness/patterns/test-driven.md
harness/patterns/ui-ux.md
harness/patterns/tech-stack.md     ← generic stack-agnostic rules (the chosen stack is in spec/architecture.md)
harness/patterns/code.md           ← generic code conventions
harness/patterns/agentic-ai.md     ← OPTIONAL catalogue of agentic patterns — only relevant if spec/agent.md exists
harness/rules/git.md
```

**`spec/agent.md` and `harness/patterns/agentic-ai.md` are OPTIONAL.** Most projects (a website, a CRUD
app, an internal tool) have no AI-agent/LLM-orchestration component and will never touch either file —
that's expected, not a gap. They apply only when a capability is itself built as an LLM agent (tool-use
loop, multi-step graph, multi-agent system).

## If the Spec Is Not Ready

Tell the user to run **`/zero-shot-build [their idea]`**. That skill runs one intake round — the only
interactive setup step. It may ask additional clarifying questions, and requests any secrets/API keys
the chosen stack needs, into `.env`. Once intake completes, the **agent-builder** orchestrator runs
design → scaffold → build, one phase per invocation. It is autonomous *within* a phase and stops at each
phase boundary for a **human testing gate** — the user tests the increment before the next phase starts.
Each phase delivers the smallest user-testable win, built first-time-right on the tested path.

## Skills (entry points)

These are the entry points. All are manual (`disable-model-invocation: true`). Each is invocable as a
skill **and** as a slash command (`.claude/commands/<name>.md` defers to the skill — the skill is the
source of truth, so the two never drift).

| Skill / command | Purpose |
|-----------------|---------|
| `/zero-shot-build [idea]` | Idea → working, verified increment (drives the agent-builder). Also adds a new capability to an existing spec. |
| `/zero-shot-fix [target]` | Diagnose + fix a bug, error, failing test, or spec/code drift, then verify. |
| `/zero-shot-sync [scope]` | Reconcile spec ↔ code so they match (spec wins), then verify. |

## Key Rules (summary — full rules in harness/rules/ai-agents.md)

- Never write application code before reading the full spec
- Never skip a phase — complete phase N before starting phase N+1
- Commit every logical unit of work; never let the working tree stay dirty
- Each phase is tested by the human before the next phase starts — stop at the phase boundary, hand off the test instructions, and wait for the user
- Tight scope, first-time-right — each phase is the smallest user-testable win and must work the first time the user tests it; zero rough edges on the tested path
- Tests and gates run against real dependencies (real APIs/keys from `.env`, the production-shaped database) per `harness/patterns/tech-stack.md` — never gate the build on an offline/stubbed substitute
- When in doubt, ask at intake — do not guess requirements; once intake completes, build a phase autonomously and stop for the human testing gate

## Existing codebases

This harness works just as well bolted onto an already-existing project as it does building one from
scratch. If `spec/architecture.md` still says `<!-- FILL IN -->` but real application code already
exists in the repo, the first `/zero-shot-build` run should document the **current** stack and structure
in `spec/architecture.md` and `harness/patterns/project-layout.md` (as the project's own section, not the
generic doctrine) before planning new phases — never scaffold a parallel skeleton next to code that
already works.

## Sub-agents (the team)

`/zero-shot-build` delegates a full build to **agent-builder**, which plans and coordinates the rest and
owns git/PR. `/zero-shot-fix` and `/zero-shot-sync` call the workers directly (no agent-builder) and own
git themselves. Each agent is one full, self-contained definition at `.claude/agents/<name>.md`.

| Agent | Role | Tools |
|-------|------|-------|
| agent-builder | Orchestrator — plans phases, fans out code-generator instances per slice (in parallel), and owns the git/PR surface for a build | Read, Glob, Grep, Bash, Agent |
| spec-writer | The single design authority — writes the FULL spec (incl. architecture + phased plan, and the agent-graph only if applicable) **and** self-reviews it | Read, Write, Edit, Glob, Grep |
| code-generator | Implements ONE independent slice (any surface the stack defines — e.g. backend + frontend, or a single service) plus tests — spawned in parallel, one per slice | Read, Write, Edit, Glob, Grep, Bash |
| qa-auditor | Independent review **and** run gates/tests/app **and** audit spec↔code drift; runs FIRST in fix/sync and classifies root cause SPEC-vs-CODE | Read, Glob, Grep, Bash (read-only use) |

Pattern: **spec-writer** writes the whole spec and carves each phase into independent slices.
**agent-builder** fans out one **code-generator** per slice in a single Agent message (max parallelism —
disjoint paths, never conflict). **qa-auditor** independently gates each slice and audits drift — it
never edits. The **human tests between phases**.
