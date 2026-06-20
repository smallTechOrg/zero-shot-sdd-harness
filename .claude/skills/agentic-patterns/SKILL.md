---
name: agentic-patterns
description: How to build the agentic parts of an app — control loop, tools, memory, retrieval, etc. Load on demand when implementing agent behaviour; never preload.
---

# agentic-patterns

Deep, on-demand knowledge for building agentic AI apps — paged in only when a change actually needs it, so
it never bloats the always-on context.

Each pattern is added the first time we build something that needs it, pinned to **current** library
versions at that moment (verify before pinning — a guessed version fails). Keep each to the minimum that
works; salvage the proven shapes from the old `harness/patterns/` (in git history), leaving the bloat behind.

## Patterns (filled as we build)
- _control loop (ReAct) — TBD_
- _tools — TBD_
- _memory · retrieval · persistence · observability — TBD_

Rule: a pattern earns its place only when a current capability needs it. **No speculative layers.**
