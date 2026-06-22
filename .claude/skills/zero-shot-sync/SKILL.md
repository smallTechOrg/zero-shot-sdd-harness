---
name: zero-shot-sync
description: Reconcile spec and code so they match. Audits the whole tree for drift, then brings code in line with the spec (spec wins), and verifies. Runs autonomously to a CLEAN audit.
argument-hint: [optional path or capability to scope to]
disable-model-invocation: true
allowed-tools: Bash(git*) Bash(uv run*)
---

You orchestrate a spec↔code sync. **Spec is the source of truth — when spec and code disagree, fix the code** (harness/spec-driven.md). Optional scope in `$ARGUMENTS` (a path or capability); otherwise sync the whole project. Run autonomously to a CLEAN audit; pause only on a hard blocker or if a divergence reveals the *spec* is wrong (then surface it — don't silently rewrite the spec to match code).

You drive subagents directly: read-only **auditor** finds drift, **implementer** fixes code toward spec, read-only **verifier** confirms nothing broke.

## Step 1 — Audit

Invoke **auditor** (read-only, whole-tree). It returns CLEAN or a divergence table with severities. If CLEAN, report that and stop — nothing to sync.

## Step 2 — Triage divergences

For each divergence decide the direction:
- **Code is wrong, spec is right** (the common case) → fix the code. This is the default.
- **Spec is wrong, code is right** (spec is stale/incorrect) → do **not** auto-edit the spec to match code. Surface it to the user with the specific mismatch and a proposed spec change; wait for confirmation. Silently editing the spec to match code defeats spec-driven development.
- **Undocumented behavior** (code does something not in spec) → either remove it from code or, if intended, surface it as a spec addition for confirmation.

Handle High severity first, then Medium. Low (naming/style) only if in scope.

## Step 3 — Reconcile code (with intent context)

For each "code is wrong" divergence, invoke **implementer** with the spec section and the offending file. It edits code to match the spec and adds/updates a test that asserts the spec'd behavior. Group related divergences into one implementer invocation where they touch the same files.

## Step 4 — Verify

Invoke **verifier** to run the gates and confirm the reconciliation didn't break anything (tests green, offline, smoke if there's a UI). If BLOCKED, re-invoke implementer with the failure detail and loop.

## Step 5 — Re-audit

Invoke **auditor** again. Repeat Steps 2–4 until it reports CLEAN (modulo any spec-is-wrong items you've surfaced for user decision).

## Step 6 — Report

Summarize: divergences found by severity, which were fixed in code (with files + regression tests), which were surfaced as possible spec bugs awaiting user decision, and the final audit status. Confirm the implementer pushed its commits.
