# Capabilities Index

One file per capability — exactly one discrete thing the agent can do.

## Phase 1 (active)

- [Upload and Profile Dataset](upload-and-profile.md) — accept a CSV, store it, auto-profile it.
- [Ask and Answer (Agentic Analysis)](ask-and-answer.md) — plan→codegen→execute→verify→iterate
  loop returning prose + chart + the code it ran; LLM sees schema/sample/aggregates only.
- [Run-History Audit](run-history-audit.md) — durable, reproducible record of every query.

## Deferred (later phases — see [roadmap.md](../roadmap.md))

- Persistent cross-day sessions + conversation memory (Phase 2)
- Follow-up question suggestions (Phase 2)
- Multi-dataset join/compare/swap + folder source (Phase 3)
- Column annotations (Phase 3)
- Derived-dataset library (Phase 3)
- Tokens + cost accounting and running daily total (Phase 4)
- Excel + external SQL-database source (Phase 4)
