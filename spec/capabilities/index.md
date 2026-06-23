# Capabilities Index

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| Dataset Management | [dataset-management.md](dataset-management.md) | Phase 1 |
| Natural Language Querying | [natural-language-querying.md](natural-language-querying.md) | Phase 1 |
| Rich Responses | [rich-responses.md](rich-responses.md) | Phase 1 |
| Persistent Sessions | [persistent-sessions.md](persistent-sessions.md) | Phase 1 |
| SQL / Data Audit Log | [sql-audit-log.md](sql-audit-log.md) | Phase 1 |
| Token Economy | [token-economy.md](token-economy.md) | Phase 1 |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning
