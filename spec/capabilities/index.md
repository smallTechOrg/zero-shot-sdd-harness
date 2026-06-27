# Capabilities Index

## Capabilities in This Project

| Capability | Phase | File |
|---|---|---|
| CSV Analysis | Phase 1 | [csv_analysis.md](csv_analysis.md) |
| SQL Connectivity | Phase 2 (stub — not yet implemented) | [sql_connectivity.md](sql_connectivity.md) |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning
