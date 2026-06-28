# Capabilities Index

> **Boilerplate status:** The spec-writer sub-agent creates one file per capability in this directory. Each file describes exactly one discrete thing the agent can do.

---

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs. Examples:
- "Search the web for companies matching criteria X"
- "Draft a personalized email given a lead profile"
- "Send a Slack notification when a threshold is crossed"

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Upload & profile a CSV | 1 | [upload-dataset.md](upload-dataset.md) |
| Answer a question by executing code locally | 1 | [analyze-question.md](analyze-question.md) |
| Auto-profiling + follow-up suggestions | 2 | [auto-profile-followups.md](auto-profile-followups.md) |
| Dataset library + resumable sessions | 3 | [library-sessions.md](library-sessions.md) |
| Multi-file joins & compares | 4 | [multi-file.md](multi-file.md) |
| Full audit-trail history + cost tracking | 5 | [history-cost.md](history-cost.md) |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning

## Capability File Template

Each capability file should answer:
- **What it does** (one sentence)
- **Inputs** (what data it receives)
- **Outputs** (what it produces)
- **External calls** (APIs, LLMs, databases it touches)
- **Error cases** (what can go wrong and how it's handled)
- **Success criteria** (how we test it)
