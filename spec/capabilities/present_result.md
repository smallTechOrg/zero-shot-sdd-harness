# Capability: Present Result

## What It Does
Surfaces a completed analysis to the user as a plain-language answer alongside the executed analysis code and the intermediate steps — the "show its work" requirement.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| analysis record | `analyses` row | local SQLite (via `analyze_question`) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| result view | rendered UI: answer + code block + steps | browser at `http://localhost:8001/app/` |
| analysis JSON | `data` (answer, code, steps, result_value, status, attempts) | `GET /analyses/{id}` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (none) | reads from local SQLite only | `NOT_FOUND` (404) if the analysis id is unknown |

## Business Rules
- The executed `code` and the `steps` (captured output) are ALWAYS shown on a completed analysis — never only the final answer. This is non-optional.
- The code block is rendered monospace and expanded by default; steps are shown in a collapsible block.
- On `status=failed`, the user sees a plain-language failure message (the `answer`) plus the last attempted code/steps — never a raw stack trace as the headline.
- Deferred features (Excel, charts, history) appear as clearly-labelled "Coming soon" non-functional stubs, not as broken controls.

## Success Criteria
- [ ] After a successful analysis, the page displays the plain-language answer AND a visible code block containing the executed pandas code AND the steps/output.
- [ ] `GET /analyses/{id}` returns the same answer + code + steps for a completed analysis.
- [ ] A failed analysis shows a readable failure message, not a raw traceback, while still exposing the last attempted code/steps.
- [ ] The Excel, Visualize, and History controls are visibly labelled "Coming soon" and disabled.
