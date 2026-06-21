# SDD Agent Harness

A spec-driven development harness for building AI agents with Claude Code.

Describe what you want to build. The harness takes it from brief to working, tested,
deployed agent — spec first, no shortcuts.

---

## How it works

```
brief → spec (FR) → phases → code → tests → deploy → reconcile ↺
```

1. **Researcher** elicits requirements and writes a Feature Request
2. **Planner** slices the work into value-ordered phases with gate tests
3. **Executor** implements each phase in `src/` — exactly what the spec says
4. **Reviewer** guards the goal — nothing ships without sign-off
5. **Deployer** ships it — local demo first, cloud on request
6. **Analyser** closes the loop — detects drift, routes corrections

The loop runs autonomously after one human-touch approval gate.

## Quick start

```bash
git clone https://github.com/smallTechOrg/sdd-agent-harness
cd sdd-agent-harness
# Open in Claude Code and run /build
```

## Structure

```
harness/    the method — rules, process, patterns (read this first)
spec/       the contract — FR/CR files, stack rules, patterns
src/        the code — written by the executor, conforms to spec
logs/       the evidence — sessions, runtime, analysis (gitignored)
.claude/    Claude Code adapter — agents, skills, hooks
```

Full documentation: [harness/README.md](harness/README.md)
