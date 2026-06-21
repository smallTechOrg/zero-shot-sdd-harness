# FR-NNN — [Title]

**Date:** YYYY-MM-DD  
**Author:** [human / researcher]  
**Status:** draft | approved | in-progress | done

> **Conventions for this file**
> - **Success Criteria use EARS** (Easy Approach to Requirements Syntax) — see the legend
>   below. Each criterion is one testable sentence the reviewer turns 1:1 into an
>   acceptance test.
> - **Write `[NEEDS CLARIFICATION: question]` inline** wherever you would otherwise guess.
>   Never silently invent a requirement. The supervisor resolves all markers in one bounded
>   clarify pass before the planner starts; resolved answers land in *Open Questions*.

---

## Problem Statement

> What pain, gap, or opportunity does this address? Who feels it and when?

<!-- One focused paragraph. No solution yet. -->

## Target Users

> Who will use this feature directly? What do they care about most?

| User | Context | Primary need |
|------|---------|--------------|
| | | |

## Success Criteria (EARS)

> How do we know this is done? Each line is **observable and testable**. Use one EARS form:
>
> - **Ubiquitous:** The `<system>` SHALL `<response>`.
> - **Event:** WHEN `<trigger>` the `<system>` SHALL `<response>`.
> - **State:** WHILE `<state>` the `<system>` SHALL `<response>`.
> - **Unwanted:** IF `<trigger>` THEN the `<system>` SHALL `<response>`.
> - **Optional:** WHERE `<feature is present>` the `<system>` SHALL `<response>`.

- [ ] <!-- WHEN a user uploads a CSV the system SHALL register it as a named dataset queryable within the same request. -->
- [ ] <!-- WHEN a user asks "show top 10 rows of <dataset>" the system SHALL return a Markdown table rendered as an HTML table in the web UI. -->
- [ ] <!-- IF the LLM provider is set to stub THEN the system SHALL pass the full unit suite with no API key and no network call. -->
- [ ] <!-- The system SHALL log every SQL execution to an audit_log row (timestamp, session_id, query_text, rows_affected, duration_ms). -->

## Non-Goals

> What is explicitly out of scope for this FR?

- <!-- e.g. "Multi-file upload — separate FR" -->
- <!-- e.g. "Authentication — not required for this milestone" -->

## Key Constraints

> Hard limits that cannot be negotiated away.

| Constraint | Value | Reason |
|-----------|-------|--------|
| Stack | <!-- e.g. Python + FastAPI + LangGraph + DuckDB --> | <!-- why --> |
| Database | <!-- e.g. DuckDB (analytics) / SQLite (relational) — local-first --> | <!-- why --> |
| Deploy target | <!-- e.g. local demo, then Render on request --> | <!-- why --> |
| API keys needed | <!-- list, e.g. GEMINI_API_KEY --> | <!-- when needed --> |
| Timeline | <!-- if any --> | <!-- why --> |

## Open Questions — clarification ledger

> Every `[NEEDS CLARIFICATION]` marker raised above is resolved here in the one clarify
> pass. Format: question → decision → who decided. An FR is not `approved` while any marker
> is unresolved.

- [ ] <!-- question + the resolved decision + who resolved it -->

## Iteration Plan

> The planner writes the value-ordered iterations here once the spec is signed off — this is
> the authoritative plan, not a copy. Each iteration: one deliverable (one sentence), one gate
> command (runs in <30s), ~15 min of executor work. Always starts with Iteration 0 (scaffold,
> `/health` 200) and Iteration 1 (first model + migration + unit test).

| #   | Deliverable                          | Gate command                | Owner stage |
|-----|--------------------------------------|-----------------------------|-------------|
| 0   | <!-- scaffold — /health green -->    | <!-- curl …/health -->      | executor    |
| 1   | <!-- first model + migration -->     | <!-- uv run pytest … -->    | executor    |

## Progress Tracker

> **Everyone updates this** — this is the single file to read to know where the work stands.
> Every stage (planner, executor, reviewer, deployer, analyser) updates the row it touches as
> control passes back to the supervisor. Status: `todo | in-progress | gate-green | accepted`.
> The analyser cross-checks this table against `logs/` on each pass — a row claiming
> `gate-green` with no matching gate output in the session report is drift.

| Iteration | Status      | Gate output (logs ref)        | Reviewer sign-off | Last updated |
|-----------|-------------|-------------------------------|-------------------|--------------|
| 0         | <!-- todo --> | <!-- logs/sessions/… --> | <!-- ✔ / — -->    | <!-- date --> |
