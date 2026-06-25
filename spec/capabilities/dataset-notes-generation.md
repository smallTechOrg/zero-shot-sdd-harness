# Capability: On-demand Dataset Notes Generation (C30)

## What It Does
Generates plain-language notes describing a dataset from a sample of its rows, on upload (async) or on demand.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset id | string | `POST /datasets/{id}/describe` or upload | yes |
| 50-row sample | DataFrame | dataset | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| notes (≤300 words) | text | `datasets.context` |
| auto_notes_status | string | `datasets` row |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM via `LLMClient` (`describe.md`) | summarize sample | `auto_notes_status=failed` |

## Business Rules
- Sample 50 rows; ask for ≤300-word plain notes; write to `context`; track `auto_notes_status` (pending→done/failed).
- On success, trigger C31 fact extraction.

## Success Criteria
- [ ] `POST /datasets/{id}/describe` sets `auto_notes_status=pending`, then `done` with non-empty notes (real Gemini).
- [ ] A generation failure sets `auto_notes_status=failed`, not a crash.
- [ ] The UI "Generate notes" poll reflects the status transitions.
