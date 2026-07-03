# Capabilities Index

One file per discrete thing the agent can do. See [roadmap.md](../roadmap.md) for how these map to phases.

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Profile a dataset on upload | 1 | [profile_dataset.md](profile_dataset.md) |
| Analyze a dataset by question (core path) | 1 | [analyze_dataset.md](analyze_dataset.md) |
| Conversation sessions (turn memory + follow-ups) | 2 | [conversation_sessions.md](conversation_sessions.md) |
| Run history (save / revisit / re-run) | 2 | [run_history.md](run_history.md) |
| Cost + live progress (tokens/$/steps) | 2 | [cost_and_progress.md](cost_and_progress.md) |

## Deferred beyond this build (no capability files yet)

Explicitly out of scope for Phases 1–2 (see [roadmap.md](../roadmap.md) → Out of Scope):
- Dataset library management: projects, rename, per-column annotations the agent uses.
- Multi-dataset targeting + auto-detection + cross-file joins/compare.
- Clarifying-question gate before ambiguous runs; explicit out-of-scope detection.
- Proactive follow-up-question suggestions and quality nudges beyond upload-time flags.
- Token-by-token answer streaming.

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer creates a new `<name>.md`, updates this index, flags dependencies, and self-reviews against the architecture and data model.
