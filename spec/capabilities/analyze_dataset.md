# Capability: Analyze Dataset

## What It Does
Answers a plain-language question about one uploaded dataset by writing pandas code, running it locally against the full data, retrying on error (bounded), and composing a verifiable answer — plain-language answer with key numbers, a short narrative, at least one chart, a summary table, and the exact code.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | str | `POST /runs` body | yes |
| question | str | `POST /runs` body | yes |
| schema + sample_rows + row_count | derived | `datasets` row (via `load_context`) | yes |
| full dataset file | file | `data/datasets/<id>.<ext>` (read only in the executor subprocess) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_text | str | Run row + API + UI answer block |
| narrative | str | Run row + API + UI |
| key_numbers | list[{label,value}] | Run row + API + UI |
| chart (Vega-Lite spec) | JSON | Run row + API + UI (`vega-embed`) |
| table | list[dict] | Run row + API + UI |
| generated code | str | Run row + API + UI collapsible code panel |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`generate_code`) | Write pandas from schema + sample rows + question | Fatal — run `failed`, error surfaced in body |
| pandas subprocess (`execute_code`) | Run generated code on the FULL dataset locally | Non-fatal — becomes `exec_error`, drives bounded retry; after `AGENT_MAX_CODE_RETRIES` → run `failed` |
| Gemini (`write_answer`) | Compose answer + choose chart from the aggregated result | Fatal — run `failed`; invalid chart selection degrades to a default chart, not a failure |

## Business Rules
- **Privacy:** only schema, sample rows, aggregated results, and the question ever go to the LLM — never raw rows. Enforced by `load_context` (no full-data load into state) and by running code in a subprocess.
- **Full-data correctness:** the answer's key number must reflect a computation over **all** rows, not a sample.
- **Bounded iterate-until-right:** on an execution error the model sees its prior code + the error and retries, up to `AGENT_MAX_CODE_RETRIES` (default 3); no user re-prompt needed.
- Generated code must produce a **compact aggregated** `result` (≤ ~200 rows) suitable for the table and chart.
- The exact final code is always returned for audit.
- Runs synchronously; returns the full result in the `POST /runs` response.

## Success Criteria
- [ ] A group-by/aggregation question on a 50k-row fixture returns a key number **equal to the independently-computed full-data value** (sample ≠ full is designed into the fixture).
- [ ] The response includes a non-empty `answer_text`, at least one valid Vega-Lite `chart`, a non-empty `table`, and the exact `code`.
- [ ] When the first generated code raises (e.g. references a non-existent column), the run still completes with a correct answer after a bounded retry, and `attempts > 1`.
- [ ] The `generate_code` prompt payload provably contains only schema + sample rows + question — no full data (assertable via a log/interception in the test).
- [ ] An unrecoverable failure (e.g. still erroring after max retries) returns `status="failed"` with a non-null `error` in the body — never a silent 200 with empty content.
