---
name: zero-shot-fix
description: Diagnose and fix a problem in an existing agent — a bug description, a runtime error/stack trace, failing tests, or spec/code drift — then verify the fix. Calls the worker agents directly; runs autonomously to a verified result.
argument-hint: [bug description / error / "tests" / "drift"]
disable-model-invocation: true
allowed-tools: Bash(git*) Bash(uv run*)
---

You orchestrate a targeted fix by calling worker agents directly — no full agent-builder needed. The target is in `$ARGUMENTS` (if empty, ask what's broken). Run autonomously: classify → locate → fix → verify, looping until the failure signal is gone. Pause only on a hard blocker or explicit request.

Fixing happens in **code-generator** (it has spec intent); judging happens in read-only **qa-auditor**; pushing in **deployer**.

## Step 1 — Classify

| Signal in `$ARGUMENTS` | Done when |
|---|---|
| **Failing tests** | the gate test is green |
| **Bug description** | the wrong behavior no longer occurs and a regression test covers it |
| **Runtime error / stack trace** | the error no longer reproduces when the app runs |
| **Spec/code drift** | qa-auditor (drift mode) reports CLEAN (see also `/zero-shot-sync`) |

State your classification in one line.

## Step 2 — Locate

- **Drift / "where is this":** invoke **qa-auditor** in drift mode → it returns the specific divergence and file.
- **Bug / error:** use the built-in **Explore** agent (or Grep/Read) to find the responsible code and the repro path, keeping the search out of your context.

## Step 3 — Capture the failing signal

Invoke **qa-auditor** (gate mode) to capture the current red state — the failing test output or the reproduced error — as your before/after baseline. If you can't reproduce the reported problem, say so and ask for repro steps rather than guessing.

## Step 4 — Fix

Invoke **code-generator** with the precise target, the responsible files, and the spec sections defining correct behavior. It fixes toward spec intent and adds/updates a regression test. It must not mute a test or delete an assertion to go green; if spec and test genuinely conflict, it stops and reports (likely a spec bug → suggest `/zero-shot-sync` or a spec edit).

## Step 5 — Verify

Invoke **qa-auditor** against the Step 3 signal. Still BLOCKED → re-invoke code-generator with the new detail; loop until VERIFIED. For a drift fix, also confirm qa-auditor (drift mode) reports CLEAN.

## Step 6 — Ship + report

Invoke **deployer** to commit + push the fix. Summarize: classification, root cause (1–2 sentences), files changed, the regression test added, the verified before→after, and the pushed SHA.
