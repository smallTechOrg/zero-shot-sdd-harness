# Claude Code — entry point

A lean, Claude-Code-native **harness** for building and evolving agentic AI apps. **Code is truth; the spec
is its human-readable projection.** Read [`NORTH-STAR.md`](NORTH-STAR.md) first — the harness's own one-page spec.

## The loop
`intent → question it (plan mode) → implement in CODE → prove it → project SPEC from code → review`

## Commands
- `/new "<idea>"` — bootstrap a new app: spec → v1, one real capability, proven.
- `/change "<intent>"` — evolve an app via the loop; code + spec end in sync.
- `/sync` — re-project the spec from the current code.

## Parts
- **agents:** `spec-projector` (code→spec) · `reviewer` (diff review, fixes nothing)
- **skills:** `proof-gate` (prove it ran + gave the right answer) · `agentic-patterns` (build knowledge, on demand)
- **hook:** a Stop nudge when code changed but the spec wasn't re-projected.

Apps the harness builds live in their **own directory** — the harness never tangles into them.
