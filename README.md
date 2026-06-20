# Lean spec-driven harness

A small, Claude-Code-native harness for building and evolving **agentic AI apps** in tight, human-managed
iterations. **Code is the source of truth; the spec is its human-readable projection**, kept in sync by the
harness. The harness is the product; the apps it builds are the output, and they live in their own directories.

## Use it (in Claude Code)
- `/new "<idea>"` — bootstrap a new app (spec → a proven v1).
- `/change "<intent>"` — evolve it; code and spec end in sync.
- `/sync` — re-project the spec from the current code.

Every change runs one loop: **question the intent → implement in code → prove it ran and is right → project
the spec from the code → review.**

## What's here
```
NORTH-STAR.md     the harness's own one-page spec (read this)
CLAUDE.md         entry point Claude Code loads
.claude/
  commands/       /new · /change · /sync
  agents/         spec-projector · reviewer
  skills/         proof-gate · agentic-patterns
  hooks/          sync-nudge (spec-staleness nudge)
  settings.json   wires the Stop hook
.githooks/        secret-scan guard (no keys in commits)
```

## Principles
Lean & human-managed · code is truth · harness ≠ app · tight iteration · Claude-Code-native ·
verify-don't-trust. Full detail in [`NORTH-STAR.md`](NORTH-STAR.md).

## Status
Lean rebuild — structurally complete, **not yet exercised end-to-end**. Next step: `/new` a small app to
prove the loop and flesh out the `agentic-patterns` skill.
