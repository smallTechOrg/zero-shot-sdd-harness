# Agent Definitions (canonical)

This directory holds the **detailed, canonical definition of every agent** on the team. It is the source of truth for what each agent is, what it reads, how it behaves, and how it hands off.

## How this relates to `.claude/agents/`

Claude Code resolves agents from `.claude/agents/*.md` — each needs frontmatter (`name`, `description`, `tools`, `model`) so the **Agent tool** can invoke it. Those files are deliberately **thin indices**: identity + frontmatter + a pointer here. The full behaviour lives in this folder, one file per agent, so the rules are stated once and never drift between the registration and the definition.

```
.claude/agents/<name>.md   →  thin: frontmatter + "see harness/agents/<name>.md"
harness/agents/<name>.md   →  detailed: role, source-of-truth, inputs, procedure, output, handoff
```

When you change how an agent behaves, edit the file **here**. Only touch `.claude/agents/<name>.md` when the frontmatter itself changes (tools, description, model).

## The team

| Agent | Pair | Role |
|-------|------|------|
| [agent-builder](agent-builder.md) | orchestrator | Coordinates the whole team for a full build. Writes no spec/code. |
| [spec-writer](spec-writer.md) | maker | Writes the product spec under `spec/`. |
| [spec-reviewer](spec-reviewer.md) | checker | Independent read-only review of the spec. |
| [tech-architect](tech-architect.md) | maker+checker | Designs **and** self-reviews stack / architecture / agentic-ai / plan. |
| [code-generator](code-generator.md) | maker | Writes code + tests for one phase / one fix. |
| [code-reviewer](code-reviewer.md) | checker | Independent read-only review of the new code. |
| [qa-auditor](qa-auditor.md) | runner | Runs gates/smoke tests **and** audits spec↔code drift. Never edits. |
| [deployer](deployer.md) | git surface | Branch, commit, push, PR. The only agent that writes git history. |

Pattern: **maker → checker.** Makers are paired with independent checkers; `tech-architect` is a combined design+review role; `qa-auditor` runs (never edits); `deployer` owns version control.

## Source-of-truth docs every agent inherits

These are not restated per agent — each agent file points to the ones it must obey:

- `harness/rules/ai-agents.md` — non-negotiable session rules
- `harness/rules/git.md` — git discipline (deployer especially)
- `harness/rules/secret-hygiene.md` — secrets handling
- `harness/patterns/spec-driven.md` — spec-first discipline
- `harness/patterns/phases.md` — phase model + gates
- `harness/patterns/project-layout.md` — where code goes
- `harness/patterns/engineering-practices.md` — design/test/error/security/observability
- `harness/patterns/test-driven.md` — TDD discipline
- `harness/patterns/ui-ux.md` — UI/UX bar

## Who invokes whom

- `/zero-shot-build` skill → **agent-builder** → the rest (see [agent-builder](agent-builder.md) for the lifecycle).
- `/zero-shot-fix` and `/zero-shot-sync` skills → call workers directly (no agent-builder): `qa-auditor`, `code-generator`, `deployer` (and built-in `Explore` for bug location).
- Reference procedures: `harness/workflows/zero-shot-{build,fix,sync}.md`.
