# Workflow: Plan Review

Any plan in [`reports/`](../../../reports/) gets a staff-level review before execution.

## What a staff review checks

Read the plan front-to-back, then cross-reference against the spec. Evaluate along five axes —
in order, stop and flag on the first that fails:

1. **Spec alignment.** Does every behavioural change trace to a sentence in `spec/`? If the plan invents behaviour, the plan is wrong — the spec change is the missing first step.
2. **Phasing.** Is each phase independently verifiable (test-gated)? Are phases ordered so a partial completion leaves the repo shippable?
3. **Scope.** Anything in the plan not in the Goal? Anything in the Goal missing from the plan?
4. **Risk.** Did the plan surface the real risks, or only obvious ones? A risks section with only "might have bugs" is not serious.
5. **Reversibility.** Can each phase be reverted independently? Flag any permanent-ish changes (DB column rename, public API shape change).

## Report format

```
## Plan review: reports/<filename>

**Verdict:** Proceed | Revise | Reject

**Blocking issues** (0+)
- [phase N] <issue, with file/line pointer into plan>

**Non-blocking concerns** (0+)
- <issue>

**Missed risks** (0+)
- <risk the plan didn't surface>
```

Keep it under 300 words. Plans that need rework should say exactly what to rework.

## Constraints

- Do not edit the plan. Do not write code. Read-only.
- Do not re-plan — if the plan is wrong, explain why; the planner revises.
- Do not approve a plan that doesn't cite spec sentences for behavioural changes. That's the one red line.
