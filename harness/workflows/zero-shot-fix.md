# Workflow: Zero-Shot Fix

The procedure behind the `/zero-shot-fix` skill. Diagnose and fix a problem in an existing agent, then verify. The skill calls worker agents directly — no full agent-builder.

## When to use

A bug description, a runtime error / stack trace, failing tests, or spec/code drift. For pure drift across the whole project, prefer `/zero-shot-sync`.

## Team

| Step | Agent | Role |
|------|-------|------|
| Locate (drift) | qa-auditor (drift mode) | find the divergence + file |
| Locate (bug/error) | Explore (built-in) | find responsible code + repro path |
| Capture / verify | qa-auditor (gate mode) | red baseline, then green confirmation |
| Fix | code-generator | edit toward spec intent + regression test |
| Ship | deployer | commit + push |

## Procedure

1. **Classify** the target and state the done-condition:
   - failing tests → gate green; bug → wrong behavior gone + regression test; error → no longer reproduces; drift → qa-auditor CLEAN.
2. **Locate.** Drift → qa-auditor drift mode. Bug/error → Explore (keep the search out of main context).
3. **Capture the failing signal** with qa-auditor (gate mode) as the before baseline. Can't reproduce → ask the user for repro steps, don't guess.
4. **Fix** with code-generator: give it the target, the responsible files, and the spec sections defining correct behavior. It adds/updates a regression test. It must not mute a test or delete an assertion to go green; if spec and test genuinely conflict, it stops and reports (likely a spec bug → `/zero-shot-sync` or a spec edit).
5. **Verify** with qa-auditor against the Step 3 signal; loop code-generator ↔ qa-auditor until VERIFIED. For drift, confirm CLEAN.
6. **Ship + report:** deployer commits + pushes; report classification, root cause, files changed, regression test, before→after, and the pushed SHA.

## Gates

- A reproduction (or captured red signal) exists before any fix.
- A regression test that would have caught the problem is added.
- qa-auditor returns VERIFIED before ship; fixes never drift code from spec intent.
