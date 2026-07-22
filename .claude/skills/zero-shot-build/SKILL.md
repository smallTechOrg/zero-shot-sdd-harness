---
name: zero-shot-build
description: Turn a zero-shot idea into a perfectly-working, thoroughly-tested, spec-driven project — any language or framework. One intake round (which also collects any needed secrets into .env), then the agent-builder builds one phase at a time — autonomous within a phase, with a human testing gate between phases. Also used to add a new capability to an existing project.
argument-hint: [your idea]
disable-model-invocation: true
allowed-tools: Bash(git*) Bash(gh*)
---

You run the human channel — intake, then the testing gate at every phase boundary — and hand the
building off to the **agent-builder** orchestrator. The idea is in `$ARGUMENTS`. **If `$ARGUMENTS` is
empty, ask the user in plain text to describe their idea / the problem they want to solve, and WAIT for
their free-text reply before doing anything else.** Do NOT load `AskUserQuestion` to solicit, suggest, or
pick the idea — the idea must come from the user as their own text. Only once you have the idea do you
move to Stage 1 intake. Goal: **one prompt → a perfectly-working, thoroughly-tested project, one
user-testable phase at a time.**

This works the same way regardless of whether the idea is a website, an internal tool, a CLI, an API
service, or something with an AI-agent component — the stack is decided at intake, not assumed.

**Autonomy model:** autonomous *within* a phase; a **human testing gate between phases**. Intake is the
only interactive SETUP step; after it, agent-builder builds a phase end-to-end without pausing, then
returns a test-handoff. You present the handoff, handhold the user through testing, and only proceed to
the next phase on the user's go. agent-builder pauses mid-phase only on a hard blocker (e.g. a required
secret still missing from `.env`).

## Stage 0 — Existing codebase check

Before intake, check whether real application code already exists in this repo (beyond `harness/`,
`spec/`, `CLAUDE.md`, and this `.claude/` scaffolding). If it does:
- Skip the "what stack" portion of the technical round — read the existing code/dependency manifests
  instead and confirm the discovered stack with the user rather than asking them to choose one.
- Tell agent-builder this is an **existing-codebase build**: spec-writer documents the current structure
  in `spec/architecture.md` instead of proposing a fresh one, and no parallel skeleton gets scaffolded.

## Stage 1 — Intake (the only interactive setup step)

Intake has **two fixed sections and a variable middle**:

1. **Product rounds (variable, minimum 5)** — all product questions, progressively deeper. You keep going
   until you have resolved every dimension that would force a design decision in Phase 1. Five rounds is
   the floor; complex ideas may need 6, 7, or more. Each round covers a different dimension and must not
   repeat covered ground.
2. **Technical round (fixed, always last)** — one round of build-blockers only (stack, access method, and
   any provider/credential needs).

All rounds use `AskUserQuestion`; any secret/API-key prompt is the only additional manual step.

**How to decide when to stop product rounds:** After each round, ask: *"Is there any dimension —
interaction model, state/memory, features, constraints, edge cases, observability, integrations — that,
if left unresolved, would force spec-writer to guess?* If yes: write another product round on that
dimension. If no: move to the technical round. Err on the side of one more round rather than handing off
an ambiguous brief.

**The golden rule: Phase 1 is the smallest user-testable quick win.** Richer intake sharpens *which*
slice to build first — it does not license a bigger Phase 1. More rounds ≠ bigger scope; it means
better-scoped scope.

**Precondition: you already have the user's idea as their own free text** (from `$ARGUMENTS` or the
plain-text prompt above). Never use `AskUserQuestion` to generate or propose the idea itself.

**The cardinal rule across ALL rounds: every question and every option must be specific to THIS idea.**
After Round 1 you know the idea category — use it. A user must instantly recognise every option as being
about their thing. Generic options are a failure.

---

### Round 1 — What is the idea? (4 questions)

1. Acknowledge the idea in one sentence.
2. Ask **4 questions** via `AskUserQuestion`, all multi-select. Plain, friendly language — no technical
   jargon. Pure product questions.

   Four themes — adapt wording and all options to the idea:
   - **What it works on** *(4 idea-specific options)* — the data, content, or domain it processes. Be
     concrete.
   - **What it produces** *(4 idea-specific options)* — the output or action it delivers. Be concrete.
   - **Usage pattern** *(4 options)* — who uses it, how often, in what context.
   - **Non-negotiables** *(4 options)* — always offer at least: "My data can't leave my machine / this
     server", "Keep costs very low", "Must connect to [something they mentioned]", "None — just build it
     well".

---

### Round 2 — How users interact (4 questions)

3. Read Round 1 answers carefully. Write ALL questions and ALL options for this round as if you are a
   product designer who has used tools exactly like this.
4. Ask **4 questions**, all multi-select. Cover: session model, memory & state (what carries across turns
   or sessions), multi-item handling, and what should happen when things go wrong.

   **Skip any question if Round 1 already answered it.**

---

### Round 3 — Feature depth (4 questions)

5. Read Rounds 1–2. This round uncovers what makes the project genuinely powerful vs. a toy.
6. Ask **4 questions**, all multi-select. Cover: reasoning/processing depth, output richness, proactive
   behavior, integration surface.

   **Skip any question if already answered.**

---

### Round 4 — Constraints & scale (3 questions)

7. Ask **3 questions**, all multi-select: data scale & performance, privacy & data residency, reliability
   bar.

---

### Round 5 — Observability, trust & transparency (3–4 questions)

8. Ask **3–4 questions**, all multi-select: reasoning/process visibility, usage & cost awareness, health
   & progress visibility, logging & audit depth.

---

### Additional product rounds (as many as needed)

After Round 5, check: *"Is there any dimension that would force spec-writer to guess?"* If yes, write
another product round on that exact dimension. Common dimensions that spill over: edge cases & error
handling, collaboration & sharing, output lifecycle, onboarding & defaults, remaining feature trade-offs.

Keep going until the brief you'll write in the synthesis step would let spec-writer fill every capability
file without a single guess.

---

### Technical round — What do we need to build it? (3–4 questions, always last)

Read all prior rounds. Now ask the **technical build questions** — only genuine blockers, 3–4 total:
- **Stack preference** — language, framework, database? If Stage 0 found an existing codebase, this round
  confirms the discovered stack instead of asking the user to pick. ("No preference" on a greenfield
  build → pick a stack that fits what was actually described in the prior rounds — scale, latency needs,
  team familiarity if stated — and document it as an `Assumed:` choice; there is no single default stack
  this harness assumes.)
- **External providers, if any** *(single-select if applicable)* — e.g. an LLM provider, a payments
  provider, a maps API — only if the idea genuinely needs one.
- **How will they access it?** — Web UI in a browser, CLI in the terminal, REST API, scheduled/automated
  job. Drives whether to build a frontend.
- **One follow-up** from prior rounds only if something would force a mid-build pause — skip if
  everything is clear.

**Secrets/API keys** (the only manual user step, if the chosen stack needs any). Read `.env` and check
whether the needed variable(s) are already set (non-empty). If present and non-empty, skip silently. Only
if missing or empty, tell the user to set them in `.env` (from `.env.example`) and wait for confirmation.
Never echo, print, paste, or commit a secret value.

**Synthesis brief**: write a **2–3 paragraph brief** covering: what the project does and who uses it; the
core interaction model; the key capabilities and features; the hard constraints; and the technical stack
and access model. Name the one core path for Phase 1 explicitly — the single most important thing a user
does that proves the idea. ("Just build it" → narrow MVP, sensible stack for the described scale,
documented as assumptions.)

## Stage 2 — Design + scaffold + build Phase 1 (delegate)

Invoke the **agent-builder** sub-agent once with the brief and the populated `.env`. Tell it to run, in
order, and return the **Phase-1 test-handoff**:

- **DESIGN** — spec-writer writes the full spec: vision/capabilities, `spec/architecture.md` (incl. the
  `## Stack` section), `spec/agent.md` only if an agentic component is genuinely needed, and the phased
  plan in `spec/roadmap.md` under "## Phases of Development".
- **SCAFFOLD** — branch `feature/<slug>-v0.1`, project dirs (or confirmation of the existing layout, on an
  existing codebase), `.env.example`, first commit + push, open the PR.
- **BUILD PHASE 1** — fan out generators per independent slice in parallel, gate each slice with
  qa-auditor, then return the Phase-1 test-handoff and STOP.

Relay only the hard blockers it escalates (e.g. a required secret still missing from `.env`).

## Stage 3 — Human testing gate (you own the human channel)

Phase 1 is the smallest working win: real on the one core path, with clearly-labelled non-functional
stubs for everything coming later. **Spoon-feed the user: the ONLY things they should ever do by hand are
(a) put secrets in `.env` and (b) interact with the running app (click / chat / run a CLI command). They
must never run a build/test command themselves to verify a phase.** You own the gate, the run/serve
lifecycle, and re-invocation:

1. **Launch the app** (you own this — agent-builder does NOT start it; sub-agent background processes are
   cleaned up on return). The handoff includes the project root path + exact run command(s) for this
   project's actual stack. Run them in order, `run_in_background: true` for anything long-running, then
   health-check with retry before presenting the gate. If it never responds → route immediately to
   qa-auditor (boot failure), do not present the URL/output.
2. Present the handoff as **phase release notes**: the live URL (or CLI invocation), what was built this
   phase, what to click / type / look at, the expected result, which parts are clearly-labelled stubs vs
   real (a stub must never read as a bug), and what the next phase adds. No run commands in the handoff
   itself — the app is already serving.
3. Ask via `AskUserQuestion` — **ALWAYS MULTI-SELECT, never a single-choice verdict.** One call, tick all
   that apply, covering both load-state and a per-feature checklist derived from THIS phase's success
   criteria:
   - *"Is the app loading / running?"* → **"Yes, I can see it"** / **"No — error or blank page"**
   - *"What worked?"* (multi-select) → one option per testable feature the phase shipped, plus a
     **"Nothing worked"** escape.
   A multi-select checklist tells you *which* parts passed and *which* failed in one answer — a single
   verdict throws that away. If "No — error" or "Nothing worked" is ticked, route to qa-auditor.
4. Route on their answers:
   - App didn't load → qa-auditor (boot failure), fix, re-present.
   - Any negative verdict → capture what they saw, then delegate to **zero-shot-fix** — pass the user's
     description, the phase context, the live URL, and any qa-auditor diagnosis already in context so it
     can skip re-diagnosis. It owns diagnose → fix → verify → commit + push autonomously, using the
     **scoped gate** for small CODE fixes. When it returns VERIFIED, rebuild + restart the running app and
     **re-present** the gate. Loop until satisfied.
   - Positive only → **"Ready for Phase 2?"** → **"Yes, let's go"** / **"One more thing first"**. "One
     more thing" → route as negative above. "Yes" → Stage 4.

## Stage 4 — Per remaining phase (build → gate, repeat)

For EVERY remaining phase boundary:

1. Invoke **agent-builder** again — **one phase per invocation** — passing the user's feedback from the
   prior gate. It wires the relevant stubs into real functionality, fanning out generators per
   independent slice in parallel and gating each with qa-auditor, then returns that phase's test-handoff
   and STOPS.
2. Run the **Stage 3 human testing gate** again for this phase.

Repeat until no phases remain.

## Stage 5 — Ship + report

1. **qa-auditor** — final whole-tree drift audit (CLEAN). Route any divergence per Stage 3 and
   re-verify.
2. **agent-builder** — ensure the final state is pushed and the PR body is current.
3. Summarize for the user: what was built, the **live URL/command it's running at** (keep it serving),
   what's deferred, and the PR link. Run commands belong in the README for the record — not as something
   the user must execute to test.

## Adding a capability to an existing project

If the spec is already filled in and the user is adding a capability: skip the scope intake; confirm the
existing `.env` already holds the needed secrets and ask only if the new capability requires a new
provider/credential. Tell agent-builder to run **spec-writer** (it owns architecture + roadmap now: add
the capability to the spec and append an incremental phase to `spec/roadmap.md`, self-reviewed) → fan out
the generators per slice → gate with qa-auditor. Then run the **human testing gate** on the new phase,
same as any other.
