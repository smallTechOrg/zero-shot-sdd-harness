---
name: build
description: Run the build workflow — take an idea or spec from zero to a working, reviewed, user-testable delivery of a phase. Use when building something new from a brief or an approved spec.
user-invocable: true
---

# /build

Read `harness/process/workflows/build.md` and follow it exactly.

You are the **supervisor** (the root session). Before anything else:

1. Read `harness/rules/non-negotiables.md`; skim `harness/rules/gotchas.md` for the stack section.
2. Open or continue the session report in `logs/sessions/` (narrative log + latency ledger).
3. Check spec readiness:
   - `spec/` docs are still placeholder templates → no spec yet. Run the **researcher** to author the
     spec (`vision.md`, `architecture.md`, `data-model.md`, `api.md`, `ui.md`, `agent-graph.md`,
     `delivery-plan.md`) from the brief. No application code until the spec is signed off.
   - `spec/` docs are filled in → read them, then run the pipeline for the current phase.

Then run the pipeline `researcher → planner → executor → reviewer → deployer → analyser ↺` as a
**swarm** (parallel steps where independent), gathering at the phase gate.

**Coordination:** the planner writes the current-phase Step DAG + Progress Tracker to the single
hardcoded path `logs/PLAN.md`; every sub-agent reads/writes it. The durable phase roadmap lives in
`spec/delivery-plan.md`. The session report holds only the narrative log + latency ledger.

One **phase** = one user-testable increment, built as parallel **steps**. Steps gate green; the
phase gates hard at the one user-acceptance boundary. Only you (the supervisor) ask the user
questions, and every such question uses the `AskUserQuestion` tool.
