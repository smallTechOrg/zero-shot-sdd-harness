---
name: zero-shot-build
description: Turn a zero-shot idea into a working, tested, spec-driven agent skeleton. One intake round, then fully autonomous to a verified Phase-2 skeleton. Also used to add a new capability to an existing agent.
argument-hint: [your idea]
disable-model-invocation: true
allowed-tools: Bash(git*) Bash(uv run*) Bash(gh*)
---

You are the orchestrator for a zero-shot build. The idea is in `$ARGUMENTS` (if empty, ask for it once). **Intake-only autonomy:** ask the upfront questions, get one approval, then run fully autonomously through spec → tech → plan → build → verify. Do not pause between stages. Pause only on a hard blocker (missing required API key, a spec/code conflict you cannot resolve, a gate that fails after a genuine fix attempt) or if the user explicitly asks.

You drive the subagents directly — there is no master builder agent. Each subagent writes durable files; you read those files, not its chat history.

## Goal

**One prompt → working skeleton in ~10 minutes.** Phase 2 runs the core loop end-to-end with stubs, fully offline.

## Stage 1 — Intake (one round)

1. Acknowledge the idea in one sentence.
2. Load the question tool: `ToolSearch` with query `select:AskUserQuestion`. Do this before asking.
3. Ask **one round** of 4 questions via `AskUserQuestion`:
   - **MVP scope** — minimum to call it working? (narrow core loop / full set / in-between)
   - **Stack** — language, database, hosting? ("no preference" → you propose defaults in the approval summary)
   - **Output/trigger** — how is it invoked, what does it produce? (webhook / schedule / CLI / API → JSON / DB / email …)
   - **Key constraints** — API keys they have, hard no's, compliance, systems to integrate.
4. Synthesize answers into a one-paragraph brief.

If the user said "just build it": narrow MVP, Python + PostgreSQL defaults, include in the approval summary.

## Stage 2 — Draft (autonomous)

Run in sequence, passing each artifact via disk:
1. Invoke **spec-author** with the brief → writes `spec/` (ruthless 2–4 capabilities, rest deferred).
2. Invoke **tech-designer** → writes `spec/tech-stack.md`, `spec/code-style.md`, fills `spec/architecture.md`, and `spec/agent-graph.md` if a framework is chosen.
3. Invoke **planner** → writes `reports/implementation-plan.md` (Phase 1 + Phase 2 minimum).

If tech-designer returns an open question (e.g. database not stated), fold it into the Stage 3 approval rather than stopping.

## Stage 3 — One approval gate

Present everything in a single message: what it does (v0.1 scope, 2–4 bullets), what's deferred, the stack (with reasons for any you chose), and the Phase 1/Phase 2 plan with gate commands. Ask once via `AskUserQuestion`: **Start building / Adjust scope / Change stack / Show full spec**. "Start building" → proceed with no further prompts. This is the only gate before code.

## Stage 4 — Scaffold (before any code)

1. `git checkout -b feature/<slug>-v0.1` — **never build on `main`** (harness/ai-agents.md Rule 10).
2. Create the project directory per `harness/project-layout.md`. Never write app code at the repo root.
3. Open a session report `reports/sessions/YYYY-MM-DD-HHMMSS-<branch>.md` before Phase 1.
4. Create `.env.example` with every env var as a placeholder.
5. Commit + push, then open the PR immediately: `gh pr create --base main --head feature/<slug>-v0.1` (Rule 11 — a PR must exist before the first feature commit).

## Stage 5 — Build (autonomous, phase by phase)

For each phase in the plan (Phase 1, then Phase 2):
1. Invoke **implementer** for that phase only → it writes code + tests, runs its gate, commits+pushes.
2. Invoke **verifier** for that phase → returns VERIFIED or BLOCKED.
3. If BLOCKED, re-invoke **implementer** with the verifier's specific failures. Loop until VERIFIED. Escalate to the user only if it cannot be resolved.
Never start phase N+1 before phase N is VERIFIED.

## Stage 6 — Final check

Invoke **auditor** for a whole-tree spec/code drift check. If DIVERGENCES FOUND (High/Medium), fix via implementer and re-verify. When CLEAN and the skeleton runs, summarize for the user: what was built, how to run it (verified commands), what's deferred, and the PR link.

## Adding a capability to an existing agent

If the spec is already filled in and the user is adding a capability: skip intake scope questions, invoke **spec-author** to add just the new `spec/capabilities/<name>.md` (+ update `index.md`, touch architecture/data-model only if affected), then **planner** for the incremental phase(s), then the build+verify loop. Same autonomy rules.
