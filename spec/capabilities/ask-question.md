# Capability: Ask a Question

## What It Does
Answers a natural-language question over a profiled dataset by planning a strategy, generating dialect-safe DuckDB SQL, executing it locally (retrying on SQL error), and returning a plain-English answer with key numbers, ONE auto-picked chart, and a summary table — sending only schema + aggregates to the LLM.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | URL path | yes |
| question | string | Ask box | yes |
| schema | dict | Dataset.schema_json (loaded by runner) | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | string + key_numbers | browser answer panel |
| chart | `{type, x, y, data}` | browser (Recharts) |
| table | bounded summary table | browser |
| QuestionRun | record (plan, sql, trace, result, cost, status) | SQLite |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (`gemini-3.1-pro`) | plan + generate SQL (schema only); phrase answer (aggregate only) | set `error` → `handle_error`; run `status="failed"` with message |
| DuckDB (local) | execute generated SQL | set `sql_error` → retry loop (regenerate SQL up to 3×); on exhaustion → failed |

## Business Rules
- **Privacy boundary:** only column schema and bounded aggregates (≤ 50 rows) are ever sent to the LLM — enforced by the `privacy_guard` node. The full result table renders locally only.
- **Dialect safety:** generated SQL is DuckDB dialect; SQLite-isms (e.g. `julianday`) are forbidden in the prompt. On a SQL error the exact error is fed back to regenerate corrected SQL (≤ 3 retries) — a SQL error is never a dead end.
- One LLM plan/SQL call + bounded retries + one phrase call per question (keep cost low).
- ONE chart per answer; concise answer (answer + key numbers + one visual).
- Answer returns under ~30s.

## Success Criteria
- [ ] A factual question returns a correct answer with the right key number, verified against the full dataset (not a sample).
- [ ] The executed DuckDB SQL is returned and matches what produced the answer.
- [ ] A question that would tempt a SQLite-ism (e.g. a date-difference) succeeds — either directly in DuckDB dialect or via the retry loop, with the recovery visible in the trace.
- [ ] No raw data row appears in any logged LLM input for the run.
- [ ] The QuestionRun row persists plan, sql, trace, result summary, chart, and per-question cost, tied to the dataset.
