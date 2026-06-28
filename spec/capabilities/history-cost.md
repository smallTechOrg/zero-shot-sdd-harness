# Capability: Full Audit-Trail History + Cost Tracking  *(Phase 5)*

## What It Does
Provides a full browsable run history grouped per dataset (every question, code, result, timestamp, status) with downloadable results, plus live per-query tokens + estimated cost, a running session total, a step counter, and an elapsed timer.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | query param | no |
| run_id + fmt | string | download endpoint | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| history list | json | `GET /history` |
| tokens / cost | int / float | Run.tokens, Run.cost_usd + UI badges |
| download | csv/json file | `GET /runs/{id}/download` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | query history, persist tokens/cost | api_error |
| Gemini usage metadata | capture token counts per call | cost shown as null if unavailable |

## Business Rules
- Token counts captured per LLM call in `LLMClient`; cost estimated from a configured per-token rate.
- History is grouped by dataset and ordered by time; nothing is deleted.

## Success Criteria
- [ ] After several runs, History shows every run grouped by dataset with code/result/timestamps.
- [ ] Live badges show per-query tokens + cost, a running session total, step count, and an elapsed timer; a result downloads as CSV.
