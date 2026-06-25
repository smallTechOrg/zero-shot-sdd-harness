# Capability: NL Data Cleaning — Preview + Apply (C24)

## What It Does
Generates pandas cleaning code from a natural-language instruction, previews its effect, and applies it in place on confirmation.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset id | string | path | yes |
| cleaning instruction | string | body | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| preview | JSON | `{code, before/after row+col counts, previews}` |
| applied dataset | updated row + files | SQLite + disk |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM via `LLMClient` (`clean.md`) | generate pandas code | error surfaced |
| pandas | run on a copy (preview) / in place (apply) | 422 exec error |

## Business Rules
- `/clean` runs the generated code on a COPY and returns before/after counts + previews; never mutates.
- `/clean/apply` runs it in place, rewrites CSV + Parquet, updates counts.
- A clean exec error returns 422.

## Success Criteria
- [ ] "drop rows with nulls" preview returns generated code and correct before/after row counts without changing the dataset.
- [ ] Apply updates the dataset's row/col counts and rewrites the files.
- [ ] Invalid generated code returns 422, not a 500 crash.
