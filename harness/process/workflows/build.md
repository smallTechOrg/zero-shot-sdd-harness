# Workflow: Build

`researcher → planner → executor → reviewer → deployer → analyser ↺`

Takes a user brief from zero to a working, reviewed, locally deployed slice.
The pipeline runs autonomously after the one human-touch gate; the analyser closes the
loop back to the head on drift.

---

## Blackboard — what each stage reads and writes

| Stage      | Reads                       | Writes                                        |
|------------|-----------------------------|-----------------------------------------------|
| researcher | user's brief                | `spec/features/FR-NNN.md`, `spec/rules/`      |
| planner    | `spec/`                     | phase plan (session report)                   |
| executor   | `spec/`, phase plan         | `src/`, `tests/`, unit tests                  |
| reviewer   | `spec/`, `src/`, `tests/`   | acceptance tests, sign-off (session report)   |
| deployer   | `src/`, config              | local demo running, deploy result (session report) |
| analyser   | `spec/`, `src/`, `logs/`    | `logs/analysis/`, spec amendment proposals    |

Sub-agents share no memory between invocations. Coordination is through durable
artefacts on disk — not conversation.

---

## Stages

### 1. researcher — get the goal right

Runs the intake script (see `harness/process/agents/researcher.md`):
- **Round 1:** 4 core questions — problem, users, success criteria, constraints
- **Round 2:** 4 detail questions — integrations, non-goals, data shape, Phase 2 golden path
- **Round N:** adaptive until FR is complete or user explicitly accepts the risk of gaps
- Proposes tech stack; user approves or overrides
- Collects all API keys before sign-off; records which are present (boolean) in session report
- Writes `spec/features/FR-NNN.md` using the template in `harness/process/templates/FR.md`
- Fills `spec/rules/tech-stack.md` with the approved stack

**Gate (supervisor):** FR is complete and coherent, stack is approved, all keys identified.
After sign-off the pipeline runs autonomously, gated only by tests and user acceptance.

### 2. planner — slice by value

Slices the work into phases by end-user value — smallest end-to-end slice first.
No fixed phase list; phases are derived from the spec.

Records in the session report:
- Phase list with a one-line goal per phase
- Gate test for each phase (the specific command to run)
- Which phase is Phase 2 (the stub/offline phase — always present)

**Phase 2 requirement:** every build must have a Phase 2 that runs fully offline (no API
keys, no network, stubs only) and ends with a running local demo at `http://localhost:8001`.

### 3. executor — make the action

Implements the current phase in `src/` — exactly what the slice calls for, no more.

**Python project conventions:**
- `src/` holds all application code; `tests/` at the repo root holds all tests
- External calls (LLM, DB, API) sit behind a thin abstraction in `src/integrations/`
- Phase 2 stubs live in `src/integrations/stubs/`; stub mode is labelled on every UI page
- The Phase 2 gate must pass with no API key set — `uv run pytest` must be green offline
- `uv` is the package manager; dependencies in `pyproject.toml`

**On blocker:** if the executor cannot resolve a problem in three attempts, stop and
route to the fix workflow — do not hack around it.

### 4. reviewer — guard the goal

Reviews `src/` against the spec. Signs off the phase gate.

**Gate (all four required):**
1. Tests pass — output shown in session report, not assumed
2. Working tree clean and pushed
3. Reviewer has signed off explicitly
4. Session report updated with what was done and what is next

Nothing passes without all four. If any fails, the phase stays open.

### 5. deployer — ship it

**Phase 2 deploy (always):** spin up the local demo server; confirm `http://localhost:8001`
returns a live response. Log the curl output in the session report.

**Later phases:** deploy to Render or other targets only when the user explicitly requests
it. Never deploy to production automatically.

**Irreversible actions** (external deploys, DB migrations in production, any action that
cannot be undone): always confirm with the user via the supervisor before proceeding.

### 6. analyser — close the loop

Reads `logs/`, test results, and gate results. Compares outcome against the FR.

| Drift        | Action                                                          |
|--------------|-----------------------------------------------------------------|
| spec ≠ src   | route back to executor                                          |
| src ≠ logs   | route to fix workflow                                           |
| logs ≠ spec  | fix `src/`, or propose spec amendment if the goal was wrong     |
| all agree    | surface to user for acceptance                                  |

**Done signal:** the user explicitly accepts the phase. Tests and sign-off are necessary
but not sufficient — the analyser waits for user acceptance before declaring done.

Spec amendments (when the goal turns out to be wrong) go to the supervisor and user for
approval before any change is made to `spec/`.

---

## Session report

Each stage appends to the single session file at
`logs/sessions/YYYY-MM-DD-HHMMSS-<branch>.md`.

Required sections per stage append:
- **Stage name + timestamp**
- **Decisions made** (with rationale)
- **Gate result** (command run + output)
- **Open questions or blockers**
- **What is next**
