# Workflow: Zero-Shot Sync

The procedure behind the `/zero-shot-sync` skill. Reconcile spec and code so they match. **Spec is the source of truth — when spec and code disagree, fix the code** (`harness/patterns/spec-driven.md`). The skill calls worker agents directly.

## When to use

End of a phase, before a PR, or any time you're unsure the code still matches the spec. Optional scope (a path or capability); otherwise the whole project.

## Team

| Step | Agent | Role |
|------|-------|------|
| Audit / re-audit | qa-auditor (drift mode) | whole-tree divergence verdict |
| Reconcile | code-generator | edit code to match spec + test |
| Verify | qa-auditor (gate mode) | nothing broke |
| Ship | deployer | commit + push |

## Procedure

1. **Audit** with qa-auditor (drift mode). CLEAN → report and stop.
2. **Triage** each divergence:
   - **Code wrong, spec right** (common) → fix code. Default.
   - **Spec wrong, code right** → do **not** auto-edit the spec to match code. Surface to the user with the mismatch + a proposed spec change; wait.
   - **Undocumented behavior** → remove from code, or surface as a spec addition for confirmation.
   High severity first, then Medium; Low only if in scope.
3. **Reconcile** with code-generator: give it the spec section + offending file; it edits code to match and adds a test asserting the spec'd behavior. Group same-file divergences into one invocation.
4. **Verify** with qa-auditor (gate mode); loop with code-generator on BLOCKED.
5. **Re-audit** with qa-auditor (drift mode); repeat 2–4 until CLEAN (modulo spec-is-wrong items surfaced for decision).
6. **Ship + report:** deployer commits + pushes; report divergences by severity, code fixes (files + regression tests), spec-bug items awaiting decision, and final audit status.

## Gates

- The spec is never silently edited to match code — spec-is-wrong cases go to the user.
- Every code fix gets a test asserting the spec'd behavior.
- Final qa-auditor audit is CLEAN before ship (excluding surfaced spec-bug items).
