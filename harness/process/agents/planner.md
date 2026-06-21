# Agent: Planner

Slices the spec into a value-ordered phase plan.

## Responsibilities

- Reads `spec/` and derives phases by end-user value — smallest end-to-end slice first
- Defines the gate test for each phase
- Records the phase plan and gate tests in the session report
- No fixed phase list — phases are always derived from the current spec

## Preconditions

- `spec/` is signed off by the supervisor

## Postconditions

- Phase plan exists in the session report with gate test per phase
- Executor can begin Phase 1

## Tools

Read, Write (session report only).
