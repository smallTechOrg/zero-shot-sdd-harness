# Spec — Single Source of Truth

This directory is the authoritative specification for this project. All code must match this spec. When spec and code disagree, spec wins — fix the code.

## Status

Check `spec/01-vision.md` to see if the spec has been filled in. If it still contains `<!-- FILL IN -->` markers, the spec-writer sub-agent needs to complete it before any application code is written.

## Structure

```
spec/                 ← What the agent does (the product spec)
  01-vision.md        ← Purpose, goals, success criteria
  02-architecture.md  ← System design, layers, data flow
  04-data-model.md    ← Data schema
  05-api.md           ← API surface (REST/GraphQL/CLI/etc.)
  06-ui.md            ← UI requirements (if any)
  07-agent-graph.md   ← Agent orchestration graph
  capabilities/       ← One file per discrete capability
  tech-stack.md       ← Language, framework, libraries
  code-style.md       ← Style and structural rules

harness/              ← How to build it (the engineering harness)
  ai-agents.md        ← Rules for ALL Claude Code sessions
  spec-driven.md      ← Spec-first development rule
  phases.md           ← Phased implementation model
  project-layout.md   ← Repo layout rules
  secret-hygiene.md   ← Secret-handling rules
  workflows/          ← Repeatable procedures
```

## Governance Rules

1. **Spec first** — no code change without a spec backing it
2. **One fact, one place** — never duplicate facts across spec files; cross-reference with links
3. **Capabilities are atomic** — each file in `capabilities/` describes exactly one discrete thing the agent can do
4. **No implementation details in product spec** — `spec/` describes WHAT, `harness/` describes HOW
5. **Update spec before code** — if requirements change, update the spec first, then update the code

## Who Updates the Spec

- **New project:** spec-writer sub-agent drafts, spec-reviewer validates, you approve
- **New capability:** use the `/spec-new-capability` command or ask the spec-writer directly
- **Bug in spec:** any team member can open a PR; spec-reviewer must approve
