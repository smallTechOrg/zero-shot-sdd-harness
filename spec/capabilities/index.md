# Capabilities Index

One file per capability. Active = Phase 1 (the privacy proof). Deferred capabilities are listed with their target phase and have their own files for design continuity.

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Ingest & auto-profile a dataset | 1 (active) | [ingest-profile.md](ingest-profile.md) |
| Plan & generate local analysis code | 1 (active) | [plan-generate-code.md](plan-generate-code.md) |
| Execute analysis locally (privacy boundary) | 1 (active) | [execute-locally.md](execute-locally.md) |
| Stream answer & show code | 1 (active) | [stream-answer.md](stream-answer.md) |
| Conversational memory | 2 (deferred) | [conversational-memory.md](conversational-memory.md) |
| Visual results (charts/tables) + follow-ups + cost meter | 2 (deferred) | [visual-results.md](visual-results.md) |
| Library, cross-file compare, Excel, audit & clarify | 3 (deferred) | [library-audit.md](library-audit.md) |

## How to Add a New Capability

Run `/zero-shot-build [description]`. The spec-writer creates `<name>.md`, updates this index, flags dependencies, and self-reviews against the architecture and data model.
