# Capability: Staged Client-side Upload Queue (C17)

## What It Does
Stages selected files in the UI with editable metadata and uploads them concurrently with inline 409 resolution.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| staged files | UI state | drag-drop / choose | yes |
| per-file rename/notes/notes-file | UI edits | user | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| upload results | per-file status | UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| `POST /upload` | upload each staged file | 409 → inline "Use existing / Upload anyway" |

## Business Rules
- Upload at most 3 concurrent; per-file state (queued/uploading/done/error).
- A 409 surfaces inline with "Use existing" (skip) or "Upload anyway" (`force=true`).

## Success Criteria
- [ ] Staging 5 files uploads them with ≤3 in flight at once and per-file status shown.
- [ ] A duplicate in the batch surfaces an inline 409 resolver without blocking the others.
