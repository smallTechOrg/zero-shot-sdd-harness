# AI Agent Boilerplate — Spec-Driven, Zero-Shot to Working Agent

This is a boilerplate for building AI agents spec-first. Give it a one-line idea. Walk away with a working, tested, phased agent.

---

## What This Is

A starting point for anyone who wants to build an AI agent without writing boilerplate from scratch. The repo ships with:

- A structured **spec template** covering product vision, architecture, capabilities, data model, API, and UI
- Three **zero-shot skills** (`/zero-shot-build`, `/zero-shot-fix`, `/zero-shot-sync`), each also available as a slash command
- A five-agent **team** — agent-builder orchestrates (and owns git/PR); spec-writer is the single design authority (writes the full spec incl. architecture + agent-graph + phased plan, self-reviews); frontend-code-generator and backend-code-generator build independent slices in parallel; qa-auditor independently reviews, runs the gates, and audits drift
- Engineering rules in `harness/` so every Claude Code session is consistent
- Phase-gated implementation — the smallest user-testable win first, then iterative expansion, with maximum parallelism inside each phase
- A human testing gate between phases — autonomous *within* a phase, you test each increment before the next phase starts
- Real-key testing — every phase gate runs against the live LLM/API using keys from `.env`

---

## How to Use This

### Step 1 — Clone and configure

```bash
git clone https://github.com/smallTechOrg/ai-spec-driven-boilerplate.git my-agent
cd my-agent
cp .env.example .env
```

### Step 2 — Open in Claude Code (or any AI coding assistant)

```bash
claude
```

### Step 3 — Kick off the build with your idea

```
/zero-shot-build An agent that monitors my Shopify store for low-inventory products and automatically drafts restock emails to suppliers
```

`/zero-shot-build` asks a short round of intake questions up front — including which API keys to put in `.env` — then builds one phase at a time, stopping at each phase boundary for a human testing gate so you test the increment before the next phase starts.

---

## What Happens Next (Intake, Then a Phase at a Time)

`/zero-shot-build` runs one intake round, then hands off to the **agent-builder**, which coordinates the team:

```
Your idea
    ↓
INTAKE — scope, stack, LLM provider, output/trigger, constraints; fill .env with the required API keys
         (may ask extra clarifying questions up front)
    ↓
[spec-writer]  → Writes the FULL spec — architecture + agent-graph + the phased plan —
                 and self-reviews it (ruthless, smallest-first scope)
    ↓
[agent-builder] → Feature branch + PR before the first commit, then scaffold
    ↓
per phase:  fan out, in parallel, one generator per independent slice
            [frontend-code-generator] ┐
            [backend-code-generator]   ├→ [qa-auditor per slice] → [agent-builder]
            [backend-code-generator]  ┘   gate + run                commit+push
            ↑___ loop only a BLOCKED slice; others are unaffected ___↑
    ↓
HUMAN TESTING GATE — agent-builder returns the phase test-handoff; YOU test the
                     increment. "Works as expected?" → continue, or report an issue
    ↓
(issue → qa-auditor diagnoses SPEC-vs-CODE → the right generator fixes → re-gate)
    ↓
repeat for every phase boundary, then SHIP — final whole-tree drift audit (CLEAN)
```

**Nothing is skipped.** Inside a phase, every slice that *can* run concurrently does — frontend and backend generators build disjoint surfaces in parallel, then qa-auditor gates each slice against the real LLM/API using keys from `.env`. At each phase boundary the build **stops for a human testing gate**: agent-builder hands you exact run commands and expected results, and the next phase starts only after you confirm. Phase 1 is the smallest user-testable win and must work first-time-right on the tested path; later phases wire stubbed surfaces into real functionality one increment at a time. After the build, fix bugs with `/zero-shot-fix` and keep spec and code aligned with `/zero-shot-sync`.

---

## Development Phases (Default Model)

| Phase | What Gets Built |
|-------|-----------------|
| 1 | Domain models + data layer |
| 2 | Core agent loop wired to the real LLM (keys from `.env`); integrations stubbed only where the external system itself isn't built yet |
| 3 | First real integration (the "happy path" end-to-end, real keys) |
| 4 | Error handling, retries, resilience |
| 5 | Remaining integrations |
| 6 | API / CLI surface |
| 7 | Basic UI (if needed) — UI tests required when a UI exists |
| 8 | Integration + edge-case + end-to-end tests (real keys) |
| 9 | Observability + logging |
| 10 | Polish, documentation, hand-off |

Each phase ends with a commit and passes QA before the next phase begins.

---

## Repo Layout

```
.claude/
  skills/           ← Entry points (/zero-shot-build, /zero-shot-fix, /zero-shot-sync) — source of truth
  commands/         ← Thin slash-command aliases that defer to the skills
  agents/           ← The team, one full self-contained definition each (agent-builder, spec-writer, frontend-code-generator, backend-code-generator, qa-auditor)
spec/               ← The product — what your agent does (you read & edit this)
  roadmap.md        ← Purpose, goals, success criteria
  architecture.md   ← System design + the chosen ## Stack
  agent.md          ← This agent's graph (if a framework is used)
  data.md  api.md  ui.md
  capabilities/     ← One file per discrete capability
harness/            ← How Claude Code should build, generically (doctrine the skills/agents cite)
  rules/            ← Mandatory rules (ai-agents, git, secret-hygiene)
  patterns/         ← phases, test-driven, project-layout, tech-stack, code, agentic-ai, …
CLAUDE.md           ← Entry point for Claude Code
.env.example        ← Environment variable template
```

There are no session logs. The record of a build is git history (`phase-N:` commits) + the PR + the per-phase test-handoff published to you at each gate.

---

## Manually Editing the Spec

If you prefer to write the spec yourself before involving AI:

1. Open `spec/roadmap.md` and fill in the placeholders
2. Work through each file in `spec/` in order
3. Once the spec is complete, run `/zero-shot-build` — it sees the filled-in spec and goes straight to planning and building

---

## Rules That AI Agents Follow

Every Claude Code session in this repo follows the rules in `harness/rules/ai-agents.md`:

- Read the full spec before writing any code
- Commit every logical unit of work (never accumulate uncommitted changes)
- One phase at a time — no skipping
- Write tests before marking a phase complete
- Tests and evals run against the real LLM/API using keys from `.env` — offline/stubbed runs are not a passing gate
- Each phase is tested by the human before the next phase starts — the build is autonomous *within* a phase, then stops at the phase boundary for the human testing gate
- Update this README whenever the project layout changes

---

## FAQ

**What if my agent needs a database?**
The spec template includes a data model section. The spec-writer sub-agent — the single design authority — will recommend the right database for your use case in `spec/architecture.md`.

**What if I already have a tech stack in mind?**
Say it in the idea: `/zero-shot-build [idea] — use Python + FastAPI + PostgreSQL`. The spec-writer honors stated stack choices as binding and skips those questions.

**What if something breaks?**
Run `/zero-shot-fix [what's broken]` — it classifies the problem (bug, error, failing test, or drift), fixes it with spec context, and verifies. The qa-auditor catches phase failures before the next phase starts.

---

## Test-Branch Workflow

The recommended way to iterate on this boilerplate:

1. Keep `main` as the clean boilerplate — only spec, engineering rules, and agent config.
2. For each build attempt, create a numbered test branch: `test-1`, `test-2`, etc.
3. Run `/zero-shot-build` with a single-line idea on the test branch. Let it build.
4. Review and test the result on that branch.
5. **Never merge the generated application code back to main.** Test branches are disposable.
6. If a run surfaces a boilerplate improvement (a clearer spec template, a missing rule), cherry-pick or manually apply that fix to `main`.

---

## Contributing

This is a boilerplate, not a framework. Improvements to the spec templates, engineering rules, agent definitions, or skills belong on `main`; generated application code does not (see Test-Branch Workflow above).
