# Capabilities Index

> One file per capability, IDs preserved from the source spec (C1–C32). The source numbering **skips C5 and C28** — both are intentional gaps in the source list, not missing capabilities; no `C5` or `C28` file exists. The 30 capabilities below are the complete set. Each file states what it does, inputs/outputs, external calls, business rules, the phase that delivers it, and testable success criteria.

---

## Capabilities in This Project

| ID | Capability | Phase | File |
|----|-----------|-------|------|
| C1 | CSV / multi-format upload | 2 | [upload-ingest.md](upload-ingest.md) |
| C2 | NL Q&A ReAct loop | 2 | [nl-qa-react-loop.md](nl-qa-react-loop.md) |
| C3 | Multi-turn conversation history | 3 | [multi-turn-conversation.md](multi-turn-conversation.md) |
| C4 | Inline Plotly charts | 4 | [inline-charts.md](inline-charts.md) |
| C6 | Markdown → HTML answer rendering | 2 | [markdown-answer-rendering.md](markdown-answer-rendering.md) |
| C7 | Per-run token tracking | 2 | [token-tracking.md](token-tracking.md) |
| C8 | Expanded result display | 2 | [expanded-result-display.md](expanded-result-display.md) |
| C9 | Session management UI | 3 | [session-management.md](session-management.md) |
| C10 | Duplicate detection | 2 | [duplicate-detection.md](duplicate-detection.md) |
| C11 | Multi-format ingest | 2 | [upload-ingest.md](upload-ingest.md) |
| C12 | Dataset context notes injection | 2 | [dataset-context-notes.md](dataset-context-notes.md) |
| C13 | Multi-file / folder drop | 2 | [multi-file-folder-drop.md](multi-file-folder-drop.md) |
| C14 | Multi-dataset querying | 3 | [multi-dataset-querying.md](multi-dataset-querying.md) |
| C15 | Dataset deletion + cascade | 2 | [dataset-deletion-cascade.md](dataset-deletion-cascade.md) |
| C16 | Notes file on upload | 2 | [notes-file-on-upload.md](notes-file-on-upload.md) |
| C17 | Staged client-side upload queue | 2 | [staged-upload-queue.md](staged-upload-queue.md) |
| C18 | Token usage widget + daily stats | 2 | [token-usage-widget.md](token-usage-widget.md) |
| C19 | Automatic dataset selection | 3 | [auto-dataset-selection.md](auto-dataset-selection.md) |
| C20 | Early exit / force-finalize | 2 | [force-finalize.md](force-finalize.md) |
| C21 | Multi-provider LLM | 2 | [multi-provider-llm.md](multi-provider-llm.md) |
| C22 | Query timer + live progress bar | 2 | [live-progress.md](live-progress.md) |
| C23 | Agent steps inspector | 2 | [steps-inspector.md](steps-inspector.md) |
| C24 | NL data cleaning (preview + apply) | 4 | [nl-data-cleaning.md](nl-data-cleaning.md) |
| C25 | Derived-dataset persistence + lineage + staleness | 4 | [derived-datasets.md](derived-datasets.md) |
| C26 | Pre-flight clarification check | 3 | [preflight-clarification.md](preflight-clarification.md) |
| C27 | Session-scoped DataFrame cache + Parquet | 3 | [dataframe-cache-parquet.md](dataframe-cache-parquet.md) |
| C29 | Live context-window display | 3 | [context-window-display.md](context-window-display.md) |
| C30 | On-demand dataset notes generation | 4 | [dataset-notes-generation.md](dataset-notes-generation.md) |
| C31 | Semantic context compression | 4 | [context-compression.md](context-compression.md) |
| C32 | Collapsible conversation turns | 3 | [collapsible-turns.md](collapsible-turns.md) |

> **C28:** intentionally absent in the source numbering — no capability, no file.

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer creates a new `<name>.md`, updates this index, flags dependencies, and self-reviews fit against the architecture and data model.
