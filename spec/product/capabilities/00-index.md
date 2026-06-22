# Capabilities Index

> **Spec status:** Capability list for the **Senior Data Analyst Agent** (`data-analyst`), v0.1. Last updated 2026-06-22. Each file describes exactly one discrete thing the agent can do.

---

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs. Examples:
- "Search the web for companies matching criteria X"
- "Draft a personalized email given a lead profile"
- "Send a Slack notification when a threshold is crossed"

## Capabilities in This Project

v0.1 is deliberately a **narrow core loop** — exactly three capabilities. Charts, dashboards, and senior-analyst workflow simulation are deferred (see `01-vision.md` → Future Phases).

| # | Capability | File |
|---|-----------|------|
| 1 | Dataset Management — upload CSV/Parquet, register in DuckDB + metadata, cache schema/samples, list | [01-dataset-management.md](01-dataset-management.md) |
| 2 | NL Cross-Dataset Query — NL → read-only SQL over one-or-more datasets, execute in DuckDB, return text + table | [02-nl-cross-dataset-query.md](02-nl-cross-dataset-query.md) |
| 3 | Audit Logging — persist every SQL/data op (prompt, SQL, row count, duration, timestamp) and view it | [03-audit-logging.md](03-audit-logging.md) |

## How to Add a New Capability

Run `/spec-new-capability [description]` or ask the spec-writer directly. The spec-writer will:
1. Create a new file in this directory
2. Update this index
3. Flag any dependencies on existing capabilities
4. The spec-reviewer will validate it fits the architecture

## Capability File Template

Each capability file should answer:
- **What it does** (one sentence)
- **Inputs** (what data it receives)
- **Outputs** (what it produces)
- **External calls** (APIs, LLMs, databases it touches)
- **Error cases** (what can go wrong and how it's handled)
- **Success criteria** (how we test it)
