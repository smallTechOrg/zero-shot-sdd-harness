# Capabilities Index

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| CSV Upload | [csv-upload.md](csv-upload.md) | Phase 1 |
| Natural Language to SQL | [nl-to-sql.md](nl-to-sql.md) | Phase 1 |
| Chart Rendering | [chart-rendering.md](chart-rendering.md) | Phase 1 |
| Insight Generation | [insight-generation.md](insight-generation.md) | Phase 1 |
| Observability | [observability.md](observability.md) | Phase 1 (cross-cutting) |

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs:

- **CSV Upload** — accept a file, parse it, load into SQLite, return schema
- **Natural Language to SQL** — convert a question + schema into a safe SELECT query and execute it
- **Chart Rendering** — deterministically choose a chart type and build a Recharts JSON spec from query rows
- **Insight Generation** — call Gemini to write a plain-English paragraph summarising the results
- **Observability** — emit structured logs per operation and propagate LLM calls to LangSmith

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning
