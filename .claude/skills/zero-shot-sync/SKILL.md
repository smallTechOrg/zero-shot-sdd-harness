---
name: zero-shot-sync
description: Reconcile spec and code so they match. Audits the whole tree for drift, brings code in line with the spec (spec wins), and verifies. Calls worker agents directly; runs autonomously to a CLEAN audit.
argument-hint: [optional path or capability to scope to]
disable-model-invocation: true
allowed-tools: Bash(git*) Bash(uv run*)
---

You orchestrate a spec↔code sync by calling worker agents directly. **Spec is the source of truth — when spec and code disagree, fix the code** (harness/spec-driven.md). Optional scope in `$ARGUMENTS`; otherwise the whole project. Run autonomously to a CLEAN audit; pause only on a hard blocker or if a divergence reveals the *spec* is wrong (surface it — don't silently rewrite the spec to match code).

Read-only **qa-auditor** finds and confirms drift; **code-generator** fixes code toward spec; **deployer** pushes.

## Step 1 — Audit

Invoke **qa-auditor** in drift mode (whole-tree). It returns CLEAN or a divergence table with severities. CLEAN → report and stop.

## Step 2 — Triage

Per divergence, decide direction:
- **Code wrong, spec right** (common) → fix the code. Default.
- **Spec wrong, code right** → do **not** auto-edit the spec to match code. Surface to the user with the specific mismatch and a proposed spec change; wait. (Silently editing the spec defeats spec-driven development.)
- **Undocumented behavior** → remove from code, or if intended, surface as a spec addition for confirmation.

Handle High severity first, then Medium; Low only if in scope.

## Step 3 — Reconcile code

For each "code wrong" divergence, invoke **code-generator** with the spec section and the offending file. It edits code to match the spec and adds/updates a test asserting the spec'd behavior. Group divergences that touch the same files into one invocation.

## Step 4 — Verify

Invoke **qa-auditor** (gate mode) to confirm the reconciliation didn't break anything (tests green, offline, smoke if there's a UI). BLOCKED → re-invoke code-generator with the detail; loop.

## Step 5 — Re-audit

Invoke **qa-auditor** (drift mode) again. Repeat 2–4 until CLEAN (modulo spec-is-wrong items surfaced for user decision).

## Step 6 — Ship + report

Invoke **deployer** to commit + push. Summarize: divergences by severity, which were fixed in code (files + regression tests), which were surfaced as possible spec bugs awaiting decision, and the final audit status.
