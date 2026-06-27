# Capabilities Index

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| File Upload | [upload.md](upload.md) | Phase 1 |
| Preset and NL Query Analysis | [preset-and-nl.md](preset-and-nl.md) | Phase 1 (summary_stats); Phase 2 (all presets); Phase 3 (nl_query) |

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs.

- **File Upload** — the user uploads a CSV or Excel file; the system saves it locally and returns metadata.
- **Preset and NL Query Analysis** — the user selects an analysis type (or types a question) and the system returns a summary, chart, and/or table. Presets run in pandas (no LLM); NL queries use Gemini.

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning
