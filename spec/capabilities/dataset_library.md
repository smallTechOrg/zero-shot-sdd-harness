# Capability: Dataset Library & Audit Trail

## What It Does
Persists datasets and full run history across sessions so the user returns over days to a library of datasets and can browse the complete audit trail (question, plan, code, result, cost, timestamps) of every analysis. Later extends to multi-file joins, derived-dataset saving, Excel multi-sheet, and a cost dashboard.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| (browse) — | none | DB query | — |
| dataset_ids | list of string | request (multi-file join, later phase) | no |
| derived_name | string | request (save derived dataset, later phase) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| datasets | list of [Dataset](../data.md#entity-dataset) summaries (name, rows, cols, uploaded_at) | response |
| conversations | list of [Conversation](../data.md#entity-conversation) with their [Turn](../data.md#entity-turn) audit records | response |
| daily_cost_total | float (running total of estimated cost) | response |
| derived dataset | new [Dataset](../data.md#entity-dataset) row + file on disk (later phase) | DB + filesystem |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | read/write dataset files | fatal for the affected request only |
| SQLite (via SQLAlchemy) | read datasets, conversations, turns; aggregate cost | fatal for the affected request only |

## Business Rules
- Every analysis turn is persisted as an immutable audit record: question, plan, code, result, token usage, estimated cost, timestamps.
- Datasets persist across sessions; the library is the landing surface the user returns to.
- Multi-file join (incl. Excel multi-sheet) and derived-dataset saving are later-phase extensions; the LLM sees only the joined profile, never joined raw rows.
- Daily cost total aggregates per-turn `estimated_cost_usd` for the current day.

## Success Criteria
- [ ] After restarting the server, previously uploaded datasets still appear in the library.
- [ ] Every completed analysis appears in the audit trail with its code, result, and cost.
- [ ] The daily cost total equals the sum of the day's per-turn estimated costs.
- [ ] (later phase) A join across two datasets produces a result without raw rows of either dataset reaching the LLM.
