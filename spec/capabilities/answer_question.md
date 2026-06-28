# Capability: Answer Question (Plan → Generate Code → Execute Locally → Answer)

## What It Does
Takes a natural-language question about a profiled dataset, plans a strategy, generates analysis code, runs that code LOCALLY against the actual file, and returns a direct answer with key numbers — showing the exact code it ran.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id | string | request | yes |
| question | string | request (user) | yes |
| conversation history | list of prior turns | DB ([Conversation](../data.md#entity-conversation)) | no (empty on first turn) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | string (direct natural-language answer with key numbers) | response + DB ([Turn](../data.md#entity-turn)) |
| plan | list of step strings | response + DB |
| code | string (the exact pandas/DuckDB code executed) | response + DB |
| result_table | JSON (the computed result frame, capped rows for display) | response + DB |
| token_usage | {prompt, completion, total} | response + DB |
| estimated_cost_usd | float | response + DB |
| status | "completed" \| "failed" | DB ([Turn](../data.md#entity-turn)) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (LLM) | plan + generate code from schema/profile + sample + question (NO raw rows) | retry once; then set error, surface "could not produce analysis" |
| Local code executor | run generated code against the file in-process | partial — capture traceback, attempt one self-correction pass; if still failing, return best-guess flagged with what it tried |

## Business Rules
- The LLM receives ONLY: the dataset profile, the N-row sample, the question, and prior conversation turns. Raw rows never leave the machine (see [privacy boundary](../architecture.md#privacy-boundary)).
- Generated code runs locally against the real file; the full result is computed over ALL rows (no sampling in the answer path).
- WHEN the question is ambiguous or the data is insufficient, the agent SHALL return a best-guess answer flagged with its assumptions and show what it tried.
- Conversation history is included so follow-ups like "now break that down by region" resolve against the prior turn.
- An answer SHALL complete within ~30s for files up to ~100MB or report a timeout.

## Success Criteria
- [ ] Asking "how many rows are there?" returns the correct count computed locally and shows the code that produced it.
- [ ] A follow-up ("now break that down by <column>") produces a grouped result that reflects the prior question's context.
- [ ] The returned `code` string, when read, matches the operation described in the `answer`.
- [ ] `token_usage` and `estimated_cost_usd` are populated and non-zero for a real Gemini call.
- [ ] The LLM request payload (asserted in tests) contains the profile + sample only — never the full row set.
