# Roadmap

> **Boilerplate status:** This file contains placeholders. The spec-writer sub-agent will fill these in based on your idea. Run `/zero-shot-build [your idea]` to start, or fill in the placeholders manually.

---

## What This Agent Does

<!-- FILL IN: One paragraph describing what this agent does, who uses it, and what problem it solves. -->

## Who Uses It

<!-- FILL IN: Primary user(s). What is their role? What are they trying to accomplish? -->

## Core Problem Being Solved

<!-- FILL IN: What manual or broken process does this agent replace or improve? -->

## Success Criteria

<!-- FILL IN: How do we know the agent is working? List 3-5 measurable outcomes. -->

- [ ] <!-- criterion 1 -->
- [ ] <!-- criterion 2 -->
- [ ] <!-- criterion 3 -->

## What This Agent Does NOT Do (Out of Scope)

<!-- FILL IN: Explicit exclusions prevent scope creep. List things the agent will never do. -->

## Key Constraints

<!-- FILL IN: Hard limits — budget, latency, compliance, API rate limits, etc. -->

## Phases of Development

<!-- FILL IN: The spec-writer fills these in. One phase = one user-testable increment, behind a human testing gate. Default each phase's slices to INDEPENDENT so generators build them concurrently; declare a dependency only when a slice truly needs another's output. Use the per-phase template below — one block per phase. -->

> **Phase 1 is the smallest first-time-right user-testable win.** It must work perfectly the first time the user tests it — zero rough edges on the tested path. Its backend is minimal but REAL on the one core path (no fake data on the tested path). Its frontend is visually complete: real UI for the one working path PLUS clearly-labelled NON-FUNCTIONAL stubs for everything coming later, so the user sees the vision (a stub must never be mistaken for a bug). Each later phase wires those stubs into real functionality, one increment at a time.

### Phase 1 — <!-- short name -->

- **Goal:** <!-- FILL IN: the single smallest user-testable win this phase delivers. -->
- **Independent slices (parallel build units):** <!-- FILL IN: each slice is a disjoint unit a single generator owns. Note its surface (frontend / backend) and any declared dependency on another slice (default: none). -->
  - `slice-a` (backend) — <!-- what it builds; deps: none -->
  - `slice-b` (frontend) — <!-- what it builds; deps: none -->
- **Key surfaces / files:** <!-- FILL IN: the files/dirs each slice touches. frontend writes the frontend surface; backend writes src/. Never the same file. -->
- **Gate command:** <!-- FILL IN: one exact runnable command that proves the phase works — real LLM/API via .env keys, production DB driver (never SQLite-as-substitute). e.g. `uv run pytest tests/test_phase1.py` -->
- **How the user tests it (handoff seed):** <!-- FILL IN: exact run command(s), what to click / look at, the expected result, and which parts are labelled stubs vs real. -->

### Phase 2 — <!-- short name -->

- **Goal:** <!-- FILL IN: next user-testable increment (typically wires a Phase-1 stub into real functionality). -->
- **Independent slices (parallel build units):**
  - `slice-a` (backend) — <!-- ...; deps: none -->
  - `slice-b` (frontend) — <!-- ...; deps: none -->
- **Key surfaces / files:** <!-- FILL IN -->
- **Gate command:** <!-- FILL IN: exact runnable command, real LLM/API + production DB driver -->
- **How the user tests it (handoff seed):** <!-- FILL IN -->

<!-- Repeat the per-phase block for every phase. -->

