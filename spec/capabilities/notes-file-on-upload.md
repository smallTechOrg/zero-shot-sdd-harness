# Capability: Notes File on Upload (C16)

## What It Does
Accepts a `.txt`/`.md` notes file alongside a data file and stores its text as the dataset context.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| notes_file | upload (.txt/.md) | `POST /upload` form | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| dataset.context | text | `datasets` row |

## External Calls
None.

## Business Rules
- Notes text is stored as `context` (≤4000 chars; truncate/validate).
- If both a form `context` and a `notes_file` are present, define a deterministic precedence (notes_file content used as context).

## Success Criteria
- [ ] Uploading a CSV with a notes file stores the notes text in `datasets.context`.
- [ ] Notes over 4000 chars are rejected/truncated per rule, not silently corrupting the row.
