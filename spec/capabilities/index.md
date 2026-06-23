# Capabilities Index

> One file per capability. Each describes exactly one discrete thing the agent can do.

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| Ingest Dataset | [ingest_dataset.md](ingest_dataset.md) | 1 |
| Answer Question | [answer_question.md](answer_question.md) | 1 |
| Enforce Read-Only | [enforce_read_only.md](enforce_read_only.md) | 1 |
| Persist Session | [persist_session.md](persist_session.md) | 1 |

Deferred (later phases, not yet capabilities): Charts (Phase 2), Multiple datasets + cross-dataset joins (Phase 3), Dashboards + audit-log viewer (Phase 4).

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer:
1. Creates a new `<name>.md` (no number prefix)
2. Updates this index
3. Flags dependencies on existing capabilities
4. Self-reviews fit with the architecture and data model

## Capability File Template

Each capability file answers: What it does (one sentence), Inputs, Outputs, External calls, Business rules, Success criteria.
