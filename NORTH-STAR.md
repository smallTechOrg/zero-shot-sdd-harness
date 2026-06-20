# North Star — the lean spec-driven harness

> The spec for the harness itself. **Code is truth; this document is its human-readable projection.**
> Keep it to one page. If it outgrows a screen, something has regressed.

## What this is
A lean, **Claude-Code-native harness** that builds and evolves agentic AI applications through tight,
human-managed iterations. The harness is the product; the apps it builds are the output.

## The model — three parts
- **HARNESS** — the tool we build and own. Independent of any app. Small enough to read end-to-end and
  hold in your head.
- **CODE** — the source of truth. Executable, tested, real.
- **SPEC** — the human-readable projection of the code: structured technical documentation, generated and
  kept in sync *from* the code. Never authoritative-but-stale.

CODE and SPEC are two sides of one coin. **The harness's only job is keeping them in sync** — and that
sync is what "spec-driven development" means here.

## The loop
```
intent → question it thoroughly → implement in CODE → project SPEC from CODE → review
```
- **Steady state is `code → spec`** — cheap, and always accurate.
- **`spec → code` is reserved** for the two moments it's actually good at: bootstrapping v1, and proposing
  a change — both gated by the "question intent" step, which interrogates the request before any edit.

## Principles
1. **Lean & human-managed.** Size is a feature. A change is reviewable by one person in one sitting.
2. **Code is truth.** No "spec is truth" fiction; no untested "core" that's really prose.
3. **Harness ≠ app.** The harness never tangles itself into the code it generates.
4. **Tight iteration.** Small, reviewable steps — no autonomous mega-rewrites that outrun comprehension.
5. **Claude-Code-native.** Built from real primitives (skills, subagents, slash commands, hooks, plan
   mode), not a giant always-loaded manual. Deep knowledge loads on demand.
6. **Verify, don't trust.** Keep the one great idea from before: prove the app *ran and gave the right
   answer*.

## Salvage from v3 (good ideas, lean re-homing)
- **Proof-it-ran gate** — done = the app booted and answered correctly, not "looks right."
- **Test-binding** — every acceptance criterion maps to a real, executable check.
- **Judge-stability** — when an LLM grades output, sample it and watch the spread.
- **Thin slice** — v1 ships one real capability + honest stubs, never five half-builds.

## Anti-goals (how the bloat crept back last time)
- A 3,000-line prose manual an AI re-types each build.
- Docs that cite files which don't exist.
- The same warning duplicated 4–5× across files.
- Layers/abstractions no current capability needs.

## The harness is good when…
- A new person reads the whole thing in ~30 minutes.
- An intent goes *questioned → code+spec changed → reviewed* in one tight loop.
- The spec always matches the code, because it is generated from it.

## Open decisions (next)
- Which Claude Code primitive implements each step of the loop.
- Where the spec-projection lives, and what triggers regeneration.
- How the proof-gate stays lean.
