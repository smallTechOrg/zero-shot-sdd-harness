# Capabilities Index

> One file per capability — one discrete thing the agent can do. No number prefixes.

---

## Capabilities in This Project (Phase 1)

| Capability | File |
|-----------|------|
| Upload CSV to Table | [upload-csv-to-table.md](upload-csv-to-table.md) |
| Natural-Language Query (Text-to-SQL) | [nl-query-text-to-sql.md](nl-query-text-to-sql.md) |
| Audit Trail | [audit-trail.md](audit-trail.md) |
| Persistent Session | [persistent-session.md](persistent-session.md) |

## Deferred (later phases — see [`../roadmap.md`](../roadmap.md))

- Multi-dataset management + cross-dataset NL joins (Phase 2)
- Charts (Phase 3)
- Dashboards (Phase 4)
- Senior-analyst workflow / multi-step planning (Phase 5)

## How to Add a New Capability

Run `/zero-shot-build [description]`. The spec-writer creates a new `<name>.md`, updates this index, flags dependencies, and self-reviews fit against the architecture + data model.
