# Capability: Analyze Question

## What It Does
Turns a natural-language question about an uploaded dataset into pandas code, executes that code locally over the full dataframe, self-corrects on errors, and produces a computed result plus a plain-language answer.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string (uuid) | `POST /analyses` | yes |
| question | string | `POST /analyses` | yes |
| schema_summary | string | `datasets` row (built by `ingest_dataset`) | yes |
| dataframe_path | string | `datasets.local_path` | yes (loaded locally at execution) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| analysis record | `analyses` row (generated_code, execution_result, execution_steps, answer, attempts, status) | local SQLite |
| analysis response | JSON `data` (analysis_id, status, answer, code, steps, result_value, attempts) | API caller / `present_result` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API (`gemini-2.5-pro`) | generate pandas code from schema_summary + question; later summarize result into plain language | surface as terminal error; never a raw traceback as the answer |
| Local sandbox (`src/execution/sandbox.py`) | execute generated code over the full dataframe | feed the error back to the LLM and retry (bounded); after `max_attempts` → `status=failed` |

## Business Rules
- Only `schema_summary` (schema + dtypes + bounded sample/profile) + the question is sent to Gemini — never the full dataset. The full dataframe is loaded from `dataframe_path` and computed over only locally.
- The answer must be **computed** by the executed code, not produced from the LLM's own guess. The result value comes from running the code; the LLM only writes the code and later explains the computed result.
- Generated code runs in a constrained environment (restricted builtins, no network, no filesystem writes, wall-clock timeout) — see `spec/architecture.md` safety note.
- On execution error, the error + previous code are fed back to the LLM to regenerate, up to `max_attempts` (default 3, `AGENT_MAX_ATTEMPTS`). Retries exhausted → `status=failed`.
- Each operation (generate, execute, retry, summarize) emits a structured log line.

## Success Criteria
- [ ] Asking a question with a known numeric answer (e.g. "average of column X") returns a `result_value` matching the value computed directly with pandas over the fixture, against the real Gemini API.
- [ ] The returned `code` references real column names from the dataset and, when run over the same dataframe, reproduces the `result_value`.
- [ ] When the first generated code raises, the agent regenerates (attempts > 1) and still returns a correct computed answer within `max_attempts`.
- [ ] No request to Gemini contains the full dataset — only schema_summary + question (verifiable by inspecting the prompt sent).
