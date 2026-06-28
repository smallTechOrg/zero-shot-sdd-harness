# Capability: Ask and Answer (Agentic Analysis)

## What It Does
Takes one plain-language question about the active dataset and runs the agentic loop
(plan → generate pandas code → execute locally → verify → iterate, up to a step cap) to return
a prose answer + key numbers + one interactive chart + the exact code it ran.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string (UUID) | prior upload | yes |
| question | string | user chat composer | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer + result + chart_spec + code | JSON | `POST /api/analyses` response → UI answer bubble |
| analysis record | row in `analyses` | DB run-history audit ([data.md](../data.md)) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-2.5-flash`) | plan + generate pandas code | loop retries; on cap-hit → status `failed` with "what I tried" |
| local executor | run generated code over full DataFrame | recoverable error → re-plan with `last_error`; fatal → `handle_error` |

## Business Rules
- The LLM receives ONLY schema, bounded sample, and aggregates — never raw rows.
- Generated code executes LOCALLY against the FULL DataFrame; numbers in the answer come from
  execution, not from the model.
- Loop iterates up to `max_steps` (default 4, env-configurable); cap-hit yields a clear failure.
- Every run is persisted (question, exact code, result, chart_spec, timestamp) — even on failure.
- Answer must complete within ~30s target.

## Success Criteria
- [ ] A grouping/aggregation question returns correct numbers verified against a direct pandas
      computation over ALL rows (sample-vs-full must differ on the test fixture — see below).
- [ ] The response includes a non-empty `chart_spec` and the exact `code` that ran.
- [ ] A first-attempt code error (e.g. wrong column name) is recovered by a retry within the cap.
- [ ] A test asserts no raw-row payload is ever included in the LLM prompt.
- [ ] The `analyses` row is written with question, code, result, chart_spec, status, timestamp.

> The gate fixture must be large enough (≥10k rows with skewed values) that an answer computed
> over the sample differs observably from the answer over the full dataset — proving execution
> runs on all rows, not the sample.
