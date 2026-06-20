---
description: Re-project the spec from the current code, so the human-readable spec matches reality.
---

# /sync — re-project the spec

Bring the spec back in line with the code (code is truth). Hand the current state to the **spec-projector**
subagent: it reads what changed (and what it touches) and rewrites the affected `spec/` docs *from the
code*. Then show a short summary of what the spec now says, and stop for your review.

Use after a code change that skipped step 4 of `/change`, or whenever the Stop hook nudges that the spec
may be stale.
