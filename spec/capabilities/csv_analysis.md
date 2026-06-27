# Capability: CSV Analysis

## What It Does

Accepts an uploaded CSV file and a natural-language question, then returns a plain-English answer and an interactive Plotly chart rendered in the browser.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| csv_file | binary (multipart/form-data) | User upload via `POST /datasets` | Yes |
| question | string | User text input via `POST /analyses` | Yes |
| dataset_id | string (UUID) | Returned by `POST /datasets`, sent with `POST /analyses` | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| answer_text | string (plain English) | `POST /analyses` response body → browser display |
| chart_json | string (Plotly JSON spec) | `POST /analyses` response body → rendered by Plotly.js in browser |
| dataset_id | string (UUID) | `POST /datasets` response body → stored in browser state for follow-up questions |
| analysis_id | string (UUID) | `POST /analyses` response body → stored in `analyses` DB table |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | `plan_analysis` node — generate analysis plan (structured JSON) | Set `state.error`; route to `handle_error`; return 200 with error field in response |
| Gemini API | `generate_answer` node — write plain-English answer from computed data | Set `state.error`; route to `handle_error`; return 200 with error field in response |
| Local filesystem | Read uploaded CSV from `data/uploads/<dataset_id>.csv` | Set `state.error`; route to `handle_error` |

## Business Rules

- CSV files must be ≤ 50 MB; reject larger files with HTTP 413.
- The agent must infer column types from the CSV (numeric, categorical, datetime) before planning analysis.
- The plan returned by Gemini must be a valid JSON object; if it is not, the `plan_analysis` node retries once before erroring.
- The Plotly chart JSON must be valid JSON conforming to a Plotly figure spec; the node validates it before writing to state.
- If a meaningful chart cannot be produced (e.g., the question is purely factual), `chart_json` is `null` and the UI shows only the text answer.
- All uploaded CSV files are stored only on the local filesystem under `data/uploads/`; their content is never sent to Gemini. Only the schema summary (column names, dtypes, sample rows, shape) is included in the LLM prompt.
- Column names and sample data included in the Gemini prompt are limited to 20 columns and 5 sample rows to keep prompt size bounded.
- The analysis result (answer + chart JSON) is persisted to the `analyses` table so the UI can re-fetch without re-running the agent.

## Success Criteria

- [ ] `POST /datasets` with a valid CSV returns HTTP 200 with a `dataset_id`, and the file is stored at `data/uploads/<dataset_id>.csv`; the `datasets` table row has correct `row_count` and `column_names_json`.
- [ ] `POST /analyses` with a `dataset_id` and a numerical question (e.g., "What is the average value of column X?") returns HTTP 200 with non-empty `answer_text` and a parseable Plotly JSON in `chart_json`.
- [ ] The `answer_text` is semantically correct for a test CSV with known values (asserted by checking that the answer contains the correct numeric result within ±1%).
- [ ] The `chart_json` is a valid Plotly figure JSON (has `data` array and `layout` object).
- [ ] If Gemini returns a non-JSON plan response, the node retries once; if both attempts fail, the analysis returns a structured error and the run status is `"failed"`.
- [ ] A CSV with >10,000 rows produces an answer that differs from an answer produced on a 5-row sample — confirming the agent operates on the full dataset.
- [ ] `POST /datasets` with a file >50 MB returns HTTP 413.
