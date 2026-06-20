---
name: proof-gate
description: Prove a change actually works — boot the app, run the real behaviour, and fail a wrong answer even on a 200. Use as step 3 of /change and before claiming anything is done.
---

# proof-gate

"Done" is not "looks right." Done = **the change ran and produced the right result**, observed this run.

## The gate
1. **Boot it.** Start the app for real (not just import it). It must come up.
2. **Run the change.** Exercise the new behaviour end-to-end, the way a user would.
3. **Judge the outcome, not the status.** Assert the *result is correct*, not just that it returned. A 200
   with a wrong answer is a FAIL.
4. **Bind every acceptance criterion to a real check.** Each criterion in the change brief maps to a test
   that actually runs. An unbound criterion is not done.

## When the result needs an LLM to judge it
For open-ended output, don't trust one verdict: sample the judge a few times and require a stable majority.
Surface disagreement instead of hiding it.

## Reporting
Report the literal result — the command, its exit status, what passed, what failed. Never report a pass you
didn't run. Fix the cause and re-run; the gate is a loop, not a checkpoint.

> The lean re-homing of v3's best idea. Concrete per-stack runners get added as we build real apps — start
> from this contract.
