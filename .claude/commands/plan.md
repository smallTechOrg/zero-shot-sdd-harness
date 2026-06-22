# /plan

Generate or regenerate the implementation plan from the current spec.

## Usage

```
/plan
```

## What It Does

Invokes the planner sub-agent (`.claude/agents/planner.md`) which:
1. Reads the current spec (`spec/` and `harness/`)
2. Produces a phased implementation plan adapted to this project
3. The plan-reviewer validates it
4. Presents the plan to you for approval

## When to Use

- After the spec and tech design are complete, before starting to build (the agent-builder does this automatically)
- When the spec has changed significantly and the existing plan needs updating
- When you want to re-scope the phases (e.g., defer some phases)

## Note

If you haven't completed the spec yet, `/plan` will tell you what's missing before it can produce a plan. Use `/build` instead to go through the full intake → spec → tech design → plan flow.
