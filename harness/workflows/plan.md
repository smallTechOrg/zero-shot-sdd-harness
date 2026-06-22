# Workflow: Draft a Plan

Per the spec-driven rule, every non-trivial multi-file change gets a written plan in
[`reports/`](../../../reports/) before any edits land.

## When to plan

- Any change that touches **three or more files**.
- Any change that touches **both spec/ and src/** in the same session.
- Any change that introduces a new capability, abstraction, or schema field.
- Any refactor whose scope is not a single function.

## Plan structure

Write `reports/<YYYY-MM-DD>-<slug>.md` with these sections, in order:

1. **Goal** — one or two sentences. What we're changing, why now.
2. **Spec impact** — which `spec/` files need edits? Draft the deltas inline.
3. **Engineering impact** — any rule in `harness/` affected? Usually no. If yes, flag.
4. **Phases** — numbered, each phase gated by a verifiable test. Example:
   - Phase 1: add domain model; test: unit tests for new model.
   - Phase 2: add tool; test: tool unit test passes.
   - Phase 3: wire into graph + CLI; test: end-to-end smoke test passes.
5. **Out of scope** — explicit non-goals to prevent scope creep during execution.
6. **Risks** — what could break, and how we'll know.

## Procedure

1. Read the relevant product spec files first. If any needed spec doesn't exist, draft it before writing the plan.
2. Bundle any ambiguity questions — one batch is better than one at a time.
3. Write the plan. Keep it terse; a good plan is scannable in under a minute.
4. Save to [`reports/`](../../../reports/) with today's date.
5. Return the path. Do **not** start implementing. The user approves first.

## Constraints

- Do not write code in the plan. Code references (class name, file path) are fine; actual function bodies are not.
- Do not commit to a library or framework choice the spec doesn't already name.
- Do not mark the plan "done" when it's written — it's done when the user approves.
