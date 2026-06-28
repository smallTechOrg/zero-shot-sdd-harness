# Capabilities Index

A capability is a single, discrete behaviour the agent performs. See [roadmap.md](../roadmap.md) for the phase each maps to.

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Profile Dataset | 1 | [profile-dataset.md](profile-dataset.md) |
| Answer Question With Code | 1 | [answer-question-with-code.md](answer-question-with-code.md) |
| Cost Accounting | 1 | [cost-accounting.md](cost-accounting.md) |
| Run History | 2 | [run-history.md](run-history.md) |
| Follow-up Conversation | 2 | [follow-up-conversation.md](follow-up-conversation.md) |
| Plan-then-Execute Deep Analysis | 4 | [plan-then-execute.md](plan-then-execute.md) |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning

## Capability File Template

Each capability file answers: What it does (one sentence) · Inputs · Outputs · External calls · Business rules · Success criteria (testable).
