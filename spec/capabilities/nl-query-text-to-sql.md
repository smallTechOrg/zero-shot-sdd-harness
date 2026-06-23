# Capability: Natural-Language Query (Text-to-SQL)

## What It Does
Turns a natural-language question about a dataset into a read-only SQL `SELECT` (via Gemini), runs it locally, and returns a formatted text answer plus the result table — without ever sending full dataset rows to the LLM.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | `POST /queries` body | yes |
| question | string | `POST /queries` body | yes |
| cached schema_text + sample_text | text | `datasets` row | yes (loaded by runner) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| generated_sql | string | `queries` row + API response |
| answer_text | string (formatted) | `queries` row + UI |
| result_columns + result_rows + row_count | JSON | `queries` row + UI table |
| status (`completed`/`failed`) + error | string | `queries` row + API response |
| audit entry (op `query`) | DB row | `audit_log` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (via `LLMClient`) | generate SQL; compose answer | set `error`, status `failed`, audit records failure |
| SQL sandbox + SQLite (`ds_<id>`) | validate SELECT-only + read-only execute | set `error`, audit records failure |

## Business Rules
- The LLM prompt for SQL contains ONLY the cached schema + ≤ 20-row sample + the question — never full rows (token economy, see [`agent.md`](../agent.md)).
- Generated SQL must be a single read-only `SELECT` referencing only the dataset's `ds_<id>` table; the sandbox rejects anything else.
- The answer is composed over the (small) result set only — the LLM does not see full rows there either.
- Result rows are capped (default 5000) before persistence/prompting.
- A failure produces `status:"failed"` with the error surfaced; no fake answer.

## Success Criteria
- [ ] A factual aggregation question (e.g. "total revenue by region") returns a correct `result_rows` set and a coherent `answer_text` grounded in those rows.
- [ ] The persisted/logged SQL prompt contains no full dataset rows (schema + ≤20-row sample only) — verifiable in a test that inspects the prompt input.
- [ ] A generated non-SELECT or multi-statement SQL is rejected by the sandbox → query `failed`, audit `success=false`, no data table mutated.
- [ ] The response includes `generated_sql`, `result_columns`, `result_rows`, and `answer_text` for a successful query.
