# Vision

> **Spec status:** Filled in for the **Senior Data Analyst Agent** (slug: `data-analyst`), v0.1. Last updated 2026-06-22.

---

## What This Agent Does

The Senior Data Analyst Agent lets a non-SQL user load several tabular datasets, ask questions about them in plain English, and receive accurate, SQL-backed answers as formatted text and tables — including questions that span more than one dataset. The user uploads CSV/Parquet files into a persistent session; the agent registers each file as a queryable table, translates each natural-language question into SQL, runs that SQL against a local analytical engine, and summarizes the result. Every data operation is recorded in an audit log. The agent is engineered for token economy: only table schemas and a handful of sample rows are ever sent to the LLM — never the raw data — and all aggregation happens in the database, not in the model's context.

## Who Uses It

- **Analysts-of-one** — a single person who owns the numbers at a small company and has no data team to lean on.
- **Data analysts** who want to explore unfamiliar CSV/Parquet extracts quickly without hand-writing exploratory SQL.
- **Product managers and operators** who routinely receive CSV exports (from a BI tool, a billing system, a CRM) and need to join and slice them to answer ad-hoc business questions.

Their shared job-to-be-done: "I have a few data files and a question that crosses them. I want a trustworthy answer without writing SQL, and I want a record of how it was computed."

## Core Problem Being Solved

Answering a cross-dataset question today means either writing SQL by hand (a skill most of these users lack) or loading everything into a spreadsheet and manually doing lookups (error-prone and impossible past a few thousand rows). Off-the-shelf "chat with your data" tools tend to (a) ship raw rows to an LLM — expensive and a data-exfiltration risk — and (b) give an answer with no auditable trail of the SQL that produced it. This agent replaces the manual-SQL / manual-spreadsheet loop with a natural-language interface that is **local-only**, **token-cheap**, and **fully auditable**.

## Success Criteria

- [ ] A user can upload two or more CSV/Parquet files into a session and they appear as queryable, listed datasets.
- [ ] A natural-language question that joins or aggregates across two datasets returns a correct text answer plus a result table, where "correct" is verified against the SQL run directly in DuckDB.
- [ ] For a routine NL→SQL question, the only dataset content sent to the LLM is the schema plus at most N sample rows per table (N small and configurable) — raw datasets never leave the machine. This is assertable by inspecting the LLM request payload.
- [ ] Every data operation (NL prompt, generated SQL, row count, duration, timestamp) is written to the audit log and is viewable in the UI.
- [ ] A session (its datasets and conversation history) survives a process restart and can be reopened.

## What This Agent Does NOT Do (Out of Scope)

For v0.1, the agent will **not**:

- Render charts, plots, or any visualization — results are **text and tables only**.
- Provide dashboards or saved/pinned views.
- Perform machine learning, forecasting, statistical modeling, or anomaly detection.
- Offer data-cleaning wizards, type-coercion UIs, dedup tooling, or fuzzy-match join helpers.
- Simulate a senior analyst's broader workflow (multi-step investigations, hypothesis trees, narrative reports) beyond the basic **plan → query → summarize** loop.
- Connect to live/remote databases or warehouses — input is uploaded files only.
- Send raw dataset rows (beyond the small sample) to the LLM, or send any data off the local machine.
- Support multi-user accounts, auth, sharing, or permissions.
- Edit or write back to user datasets — all SQL is read-only against user data.

## Key Constraints

- **Token economy (hard).** Only table schema + a small, configurable number of sample rows per table are sent to the LLM. Schemas are cached. The cheapest capable model (Gemini 2.5 Flash) is used for routine NL→SQL; escalation to a stronger model happens only when needed. All aggregation is computed in the database, never in the model context.
- **Local data only (hard).** User datasets are stored and queried locally and never leave the machine. Only schema + minimal samples reach the LLM provider.
- **Audit log mandatory (hard).** Every SQL/data operation is persisted with timestamp, originating NL prompt, generated SQL, returned row count, and execution duration.
- **Persistent sessions (hard).** A session groups its datasets and conversation history and survives process restarts.
- **Offline-capable (hard).** With no API key configured, the agent falls back to a clearly-signalled stub LLM so the app still runs and demos.

## Phases of Development

| Phase | Description | Success Gate |
|-------|-------------|--------------|
| 1 | Domain + dual store: SQLAlchemy/Alembic metadata DB (Session, Dataset, Message, AuditLogEntry) + DuckDB engine for user datasets; dataset upload + registration; schema introspection & caching | Unit tests: upload a CSV → dataset row created, DuckDB table queryable, schema cached; Alembic migration applies cleanly |
| 2 | LangGraph agent (plan → generate_sql → execute_sql → summarize → finalize, + handle_error) wired behind FastAPI web UI; ask an NL cross-dataset question end-to-end; audit log written per op; golden-path UI smoke test | Golden-path TestClient walk: create session → upload 2 datasets → ask a cross-dataset question → assert rendered answer text + table content + an audit entry exists |

## Future Phases (Deferred — not in v0.1)

1. **Charts** — render the result of a query as a chart (bar/line/scatter) inline in the chat, chosen automatically or on request.
2. **Dashboards** — pin chosen query results/charts into a persistent, refreshable dashboard view per session.
3. **Senior-analyst workflow simulation** — multi-step investigations beyond plan→query→summarize: the agent proposes follow-up questions, maintains a hypothesis trail, and produces a narrative analytical report.
4. **(Backlog)** data-cleaning helpers, live database connectors, model/forecasting capabilities, multi-user/auth.
