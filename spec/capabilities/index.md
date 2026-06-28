# Capabilities Index

> **Boilerplate status:** The spec-writer sub-agent creates one file per capability in this directory. Each file describes exactly one discrete thing the agent can do.

---

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs. Examples:
- "Search the web for companies matching criteria X"
- "Draft a personalized email given a lead profile"
- "Send a Slack notification when a threshold is crossed"

## Capabilities in This Project

| Capability | File | First active phase |
|-----------|------|--------------------|
| Profile Dataset | [profile_dataset.md](profile_dataset.md) | Phase 1 |
| Answer Question (plan → generate code → execute locally → answer) | [answer_question.md](answer_question.md) | Phase 1 |
| Visualize Result | [visualize_result.md](visualize_result.md) | Phase 1 |
| Dataset Library & Audit Trail | [dataset_library.md](dataset_library.md) | Phase 2 (stubbed in Phase 1) |

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
