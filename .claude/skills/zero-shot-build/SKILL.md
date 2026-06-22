---
name: zero-shot-build
description: Turn a zero-shot idea into a working, tested, spec-driven agent skeleton. One intake round, one approval, then the agent-builder runs the full team autonomously. Also used to add a new capability to an existing agent.
argument-hint: [your idea]
disable-model-invocation: true
allowed-tools: Bash(git*) Bash(gh*)
---

You run the intake and approval for a full build, then hand off to the **agent-builder** orchestrator. The idea is in `$ARGUMENTS` (if empty, ask for it once). **Intake-only autonomy:** ask the upfront questions, get one approval, then let agent-builder run the team to a verified skeleton. Don't pause mid-build; agent-builder pauses only on a hard blocker.

## Stage 1 — Intake (one round)

1. Acknowledge the idea in one sentence.
2. Load the question tool: `ToolSearch` with query `select:AskUserQuestion` (before asking).
3. Ask **one round** of 4 questions via `AskUserQuestion`:
   - **MVP scope** — minimum to call it working?
   - **Stack** — language, database, hosting? ("no preference" → defaults proposed at approval)
   - **Output/trigger** — how invoked, what produced?
   - **Key constraints** — API keys held, hard no's, compliance, systems to integrate.
4. Synthesize answers into a one-paragraph brief. ("Just build it" → narrow MVP, Python + PostgreSQL defaults, noted in the approval summary.)

## Stage 2 — Design (delegate)

Invoke the **agent-builder** sub-agent with the brief. It runs spec-writer → spec-reviewer → tech-architect and returns the design summary (scope, stack, plan, any open questions).

## Stage 3 — One approval gate

Present agent-builder's summary in a single message: v0.1 scope (2–4 bullets), what's deferred, the stack (with reasons), and the Phase 1/Phase 2 plan with gate commands. Fold in any tech-architect open question (e.g. database). Ask once via `AskUserQuestion`: **Start building / Adjust scope / Change stack / Show full spec**. "Start building" → tell agent-builder to proceed; no further prompts. This is the only gate before code.

## Stage 4 — Build (delegate, autonomous)

Tell **agent-builder** to run scaffold → build (per phase: code-generator → code-reviewer → qa-auditor, deployer commits) → ship (final drift check, PR updated). Relay only blockers it escalates.

## Stage 5 — Report

When agent-builder returns: summarize for the user what was built, how to run it (verified commands), what's deferred, and the PR link.

## Adding a capability to an existing agent

If the spec is already filled in and the user is adding a capability: skip the scope intake; tell agent-builder to run spec-writer (add just the new `spec/capabilities/<name>.md` + update `index.md`) → spec-reviewer → tech-architect (incremental phase) → the build loop. Same autonomy.
