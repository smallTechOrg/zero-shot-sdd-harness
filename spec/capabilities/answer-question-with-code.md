# Capability: Answer Question With Code

## What It Does
Turns a plain-language question into pandas code (written by Gemini against schema only), runs it sandboxed on the **full dataset**, and returns a plain-language answer + interactive chart + summary table + the exact runnable code.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | path | yes |
| question | string | `POST /datasets/{id}/ask` body | yes |
| profile | DatasetProfile | `datasets` row (server-loaded) | yes |
| conversation | prior-turn summaries | session (Phase 2) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text | markdown string | SSE final event + `questions.answer_text` |
| chart_spec | {type, x, y, series} | SSE + `questions.chart_spec_json` |
| summary_table | {columns, rows} (≤ MAX_RESULT_ROWS=200) | SSE + `questions.result_json` |
| code | string (runnable pandas) | SSE + `questions.code` |
| steps | step events | SSE stream (`generating_code`→`running_code`→`retrying?`→`summarising`) |
| usage | {prompt_tokens, completion_tokens, cost_usd} | SSE + `questions` (see [cost-accounting](cost-accounting.md)) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (gemini-2.5-flash) | generate pandas; summarise the result | on code-gen API error → terminal error event; on summarise error → return raw result + a generic note |
| Sandbox executor | run validated code on the full Parquet | static-reject/runtime-error/timeout/memory → retry once with error fed back, then `handle_error` ("here's what I tried") |

## Business Rules
- The LLM writes **executable code** over the full dataset — never a hardcoded op-list and never "describe a sample". See [agent.md](../agent.md) (pattern #22) and the full-data gate in [test-driven.md](../../harness/patterns/test-driven.md).
- Generated code is **statically validated** (no `import`/`open`/`os`/`subprocess`/`eval`/`exec`/dunder) before execution; the dataset is handed in as a ready `df` so code never opens files.
- Code runs in the sandbox: no network, restricted fs, 25s CPU timeout, 2GB memory cap. See [architecture.md](../architecture.md#sandboxed-code-execution).
- Raw rows never reach the LLM; only the question + profile (code-gen) and the small computed result (summarise) cross the boundary.
- Exactly **one** retry on error (Phase 1). On persistent failure, return a clear stuck message with the last code + error.
- Result rows capped at 200 for the table; the chart is driven by the computed result, not raw data.

## Success Criteria
- [ ] On a 50,000-row fixture with a pre-computed correct answer (one that a sample would get wrong), the returned answer contains the exact correct value computed from the full dataset.
- [ ] The response includes runnable code that, copied and run on the same Parquet, reproduces the result.
- [ ] An interactive chart element and a summary table render for an aggregation question.
- [ ] A question that produces a code error on the first try succeeds after the single retry (or returns a clear "what I tried" message), without crashing the server.
- [ ] A privacy test confirms no raw row value (sentinel UUID) appears in any Gemini prompt for this capability.
- [ ] A sandbox test confirms generated code attempting network/file access is rejected or fails closed, and a deliberate infinite loop is killed by the timeout.
