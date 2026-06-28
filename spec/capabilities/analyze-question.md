# Capability: Answer a Question by Executing Code Locally

## What It Does
Given a dataset and a plain-English question, the agent plans, writes pandas, runs it locally over the FULL file, retries on error, and returns a plain-English answer plus an interactive chart, a summary table, and the exact code — streaming its plan/steps/retries live and saving the full audit trail.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | path param | yes |
| question | string | request body | yes |
| schema + sample | json | Dataset (already stored) | yes |
| full CSV | file on disk | Dataset.path (local, execution only) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| plan | string | SSE `plan` event + Run.plan |
| live steps / retries | SSE events | StepStream UI |
| answer | string | SSE `final` + Run.answer |
| chart_spec | Plotly JSON | SSE `final` + Run.chart_spec_json |
| table | json records | SSE `final` + Run.table_json |
| code (audit trail) | json | Run.steps_json (every attempt) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-3.1-pro`) | plan + generate pandas (schema+sample+question only) | set `error` → `handle_error`; surfaced to UI |
| Local sandbox subprocess | run generated pandas over the full file | capture error → feed back → retry up to cap; then `handle_error` |
| SQLite | persist run + audit trail | run fails at boot if DB unavailable |

## Business Rules
- **Privacy (HARD):** only schema + ≤ 20 sample rows + the question (+ prior error on retry) reach the LLM — never the full data. See [`spec/agent.md#privacy-boundary`](../agent.md#privacy-boundary).
- The agent generates executable code, never maps onto a fixed op-list (anti-pattern `agentic-ai.md#22`).
- Retries are capped (`max_retries`, default 3); each attempt + its error is recorded.
- Code runs in an isolated subprocess with a hard timeout; namespace limited to `pd`, `np`, the DataFrame(s).
- Target end-to-end answer < ~30s on a ~100MB file.
- **Every successful answer carries a summary table** (chart optional) — reaffirms the finalize rule in [`spec/agent.md`](../agent.md) that a table is always present on success.
- **Unanswerable from this dataset:** when the question references columns absent from the loaded file, the run does NOT report a normal success — it returns the "unanswerable-from-this-dataset" state listing the columns that ARE available, surfaced through the failure channel (see [`spec/ui.md#error-states`](../ui.md)). Cross-file joins to answer such questions are the Phase 3 roadmap item.

## Success Criteria
- [ ] Asking "How many orders are there for each order_status?" over the olist CSV returns a correct count grouped by status, a bar chart spec, and a matching table — against the real Gemini API on SQLite.
- [ ] The prompt sent to the LLM contains the schema + sample but **no full-file rows** beyond the sample (asserted in a test).
- [ ] When a generated attempt raises (e.g. a wrong column name), the agent feeds the error back, regenerates, and succeeds within the cap — the retry is visible in `steps_json` and the SSE stream.
- [ ] After the run, `GET /runs/{id}` returns the persisted plan, answer, chart_spec, table, and the full per-attempt code/error audit trail.
- [ ] A computation over the full ~99k-row olist file gives a different (correct) total than the same code over only the 20-row sample — proving execution is on the full data, not the sample.
- [ ] Asking about a column not in the loaded file (e.g. `freight_value` against the 8-column `olist_orders` sample) returns the "unanswerable-from-this-dataset" state — a non-success result listing the available columns — and never a green success/AnswerCard.
