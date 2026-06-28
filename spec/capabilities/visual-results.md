# Capability: Visual Results, Follow-ups & Cost Meter (Phase 2 — deferred)

## What It Does
Renders interactive charts and summary tables from analysis results, suggests 2-3 follow-up questions after each answer, and shows token/cost per query plus a running daily total.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| exec_result | dict | execute_locally | yes |
| answer | str | summarize | yes |
| token usage | dict | LLM calls | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| chart-spec (Vega-Lite) | json | SSE `result` event → UI |
| summary table | json | SSE `result` event → UI |
| follow-up suggestions | list[str] | UI chips |
| cost/daily total | json | `GET /cost/daily` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | follow-up suggestions over result_summary | degrade: omit chips |

## Business Rules
- Chart specs built locally from aggregates (no rows in the spec beyond aggregated points).
- Chart-build failure degrades to table-only.
- Cost computed from token usage × model rate.

## Success Criteria
- [ ] A grouping result renders a chart and a table in the UI.
- [ ] 2-3 follow-up chips appear and are clickable.
- [ ] The daily total increases after a query and persists.
