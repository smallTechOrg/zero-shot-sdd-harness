# Capability: Library, Cross-File Compare, Excel, Audit & Clarify (Phase 3 — deferred)

## What It Does
Manages a library of datasets, compares across files, ingests multi-sheet Excel, browses the full audit trail, and asks a clarifying question / confirms a plan only when a query is genuinely ambiguous.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset selection | list[str] | UI library | yes |
| Excel file | upload | `POST /datasets` | no |
| question | str | query request | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| library listing | json | `GET /datasets` |
| multi-sheet profiles | json | `dataset_profiles` |
| audit trail | json | `GET /sessions/{id}/queries` |
| clarify prompt | SSE event | UI |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| openpyxl | read Excel sheets | 400 parse error |
| Gemini | ambiguity detection / plan | retry/backoff → error |

## Business Rules
- Cross-file analysis loads multiple local files in the sandbox; rows still never leave.
- Each Excel sheet gets its own profile.
- Clarify fires only when the question is genuinely ambiguous; otherwise proceed.

## Success Criteria
- [ ] The library lists all uploaded datasets and supports selecting two for a compare query.
- [ ] A multi-sheet Excel produces a profile per sheet.
- [ ] The audit trail shows every query's question, code, and result.
- [ ] An ambiguous question surfaces a clarify prompt; a clear one does not.
