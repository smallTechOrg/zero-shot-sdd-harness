# Capability: Semantic Context Compression (C31)

## What It Does
Compresses dataset notes and global memory into a short list of structured facts to keep prompts small.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| notes / memory text | text | dataset.context / settings.global_memory | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| facts (≤20) | JSON array | `datasets.context_facts` / `settings.global_memory_facts` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM via `LLMClient` (`compress.md`) | extract ≤20 facts | return `[]` |

## Business Rules
- One LLM call → JSON array of ≤20 facts.
- Async fire-and-forget self-heal variants guarded by an in-flight lock; failures return `[]`.
- Triggered after C30 notes generation and on `PATCH /memory`.

## Success Criteria
- [ ] Generating notes then compression populates `context_facts` with a JSON array of ≤20 facts (real Gemini).
- [ ] `PATCH /memory` triggers compression of `global_memory` into `global_memory_facts`.
- [ ] A compression failure leaves `[]`, not a crash, and does not block the run.
