# Capability: Cost & Live Progress

## What It Does
Makes each run transparent: streams live step-by-step progress ("Planning… / Running code… / Retrying… / Writing answer…"), records token usage and an estimated dollar cost per question with a running session/daily total, and warns before an expensive run.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question + dataset_id | str | `POST /cost/estimate`, `POST /runs` | yes |
| run_id | str | `GET /runs/{id}/progress` (SSE) | yes for progress |
| LLM usage | tokens | Gemini response metadata via `LLMClient` | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| Progress events | SSE stream `{step, detail}` | UI ProgressSteps |
| Per-run cost | `runs.tokens_used`, `runs.cost_estimate_usd` | SQLite + API + UI CostMeter |
| Session/daily total | aggregate | API + UI CostMeter |
| Expensive-run warning | `{estimated_tokens, estimated_usd, warn: bool}` | API + UI (pre-run confirm) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | Usage metadata captured in `LLMClient` wrapper | Degrade — if usage is unavailable, record null cost, do not fail the run |

## Business Rules
- Token/cost accounting is captured in the `LLMClient` wrapper so every node's usage rolls up to the run.
- Cost estimate uses the configured Gemini model's per-token price (configurable constant); it is an **estimate**, labelled as such.
- The expensive-run warning triggers above a configurable threshold and asks for confirmation before running.
- Progress steps are emitted from the graph nodes (entry of each node) over SSE and mirror the actual node the run is in, including "Retrying…" on a retry loop.
- Observability logging from Phase 1 (structlog) is the source; this capability surfaces it to the user.

## Success Criteria
- [ ] A completed run records a non-zero `tokens_used` and a non-null `cost_estimate_usd`.
- [ ] The progress SSE emits, in order, at least: planning/generating → running code → writing answer, and shows "Retrying…" when a retry occurs.
- [ ] The session total equals the sum of its runs' costs.
- [ ] A question exceeding the configured threshold returns `warn: true` from `POST /cost/estimate` before running.
