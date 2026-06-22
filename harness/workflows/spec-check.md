# Workflow: Spec Drift Check

Audit the repository for divergence between [`spec/`](../../spec/) and the project source tree,
per the rule in [`../spec-driven.md`](../spec-driven.md). Report findings as a punch list, not a narrative.

## Procedure

1. **List all capability specs.** Read every file in `spec/` (and `spec/capabilities/` when it exists). For each, extract numbered behavior steps.

2. **Locate each component in code.** For each spec'd component, find the corresponding Python module/class in `src/`. Note any that are missing entirely.

3. **Spot-check behavior steps.** For each capability, check numbered behavior steps are reflected in code. Focus on:
   - Inputs and outputs (does the function signature match the spec's Inputs/Outputs sections?)
   - Failure modes (are the specified failure modes handled?)
   - Invariants (unique constraints, idempotency)

4. **Reverse check.** For any substantial Python module/class in `src/` not matched by a spec, flag it as "unspec'd code."

5. **Check config schema.** Compare keys listed in any config spec against the pydantic models in `config/`. Flag mismatches.

6. **Check CLI/API surface.** Compare endpoints/commands in spec against registered routes/commands. Flag missing or extra.

## Report format

Output a single markdown table plus a short summary.

```
| Area | Type | Finding |
|---|---|---|
| capability: generate-post | missing behavior | Step 2 not implemented |
| api | unspec'd endpoint | POST /posts registered but not in spec |
```

Summary (1–2 lines): worst category, total count, recommended order of fixes.

## Scope

- Do **not** fix anything during the audit. Report-only.
- Do **not** propose spec changes unless asked — code fixes are almost always the answer.
- Do **not** run tests or make external API calls.
