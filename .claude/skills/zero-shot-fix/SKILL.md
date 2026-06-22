---
name: zero-shot-fix
description: Diagnose and fix a problem in an existing agent — a bug description, a runtime error/stack trace, failing tests, or spec/code drift — then verify the fix. Runs autonomously to a verified result.
argument-hint: [bug description / error / "tests" / "drift"]
disable-model-invocation: true
allowed-tools: Bash(git*) Bash(uv run*)
---

You orchestrate a zero-shot fix. The target is in `$ARGUMENTS` (if empty, ask what's broken). Run autonomously: classify → reproduce → fix → verify, looping until the failure signal is gone. Pause only on a hard blocker or an explicit user request.

You drive subagents directly. Fixing happens in the **implementer** (it has spec/plan context); judging happens in the read-only **verifier** and **auditor**.

## Step 1 — Classify the target

Decide which kind of problem this is (it may be more than one):

| Signal in `$ARGUMENTS` | Done when |
|---|---|
| **Failing tests** ("tests", a test name) | the gate test is green |
| **Bug description** (natural language) | the described wrong behavior no longer occurs and a regression test covers it |
| **Runtime error / stack trace** (a paste) | the error no longer reproduces when the app runs |
| **Spec/code drift** ("drift", "doesn't match spec") | the auditor reports CLEAN (see also `/zero-shot-sync`) |

State your classification in one line before proceeding.

## Step 2 — Locate (read-only)

- **Drift / "where is this":** invoke **auditor** → it returns the specific divergence and file.
- **Bug / error:** use the built-in **Explore** agent (or Grep/Read) to find the responsible code and the reproduction path. Keep this search out of your main context.

## Step 3 — Establish the failing signal

Invoke **verifier** to capture the current red state: the failing test output, or the reproduction of the error. This is your before/after baseline. If you cannot reproduce the reported problem, say so and ask the user for repro steps rather than guessing.

## Step 4 — Fix (with intent context)

Invoke **implementer** with: the precise target, the responsible files, and the spec sections that define correct behavior. It must fix toward spec intent — never mute a test or delete an assertion to make red go green. If the spec and a test genuinely conflict, stop and surface it (it may be a spec bug → suggest `/zero-shot-sync` or a spec edit). Add or update a regression test that would have caught this.

## Step 5 — Verify

Invoke **verifier** against the same signal from Step 3. If still BLOCKED, re-invoke implementer with the new failure detail. Loop until VERIFIED. Then, for a drift fix, also confirm **auditor** reports CLEAN.

## Step 6 — Report

Summarize: classification, root cause in one or two sentences, files changed, the regression test added, and the verified before→after (red → green, or error reproduced → gone). Commit+push are the implementer's responsibility; confirm the SHA is pushed.
