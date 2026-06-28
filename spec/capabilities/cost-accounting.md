# Capability: Cost Accounting

## What It Does
Captures token usage from every Gemini call, computes the dollar cost per question, persists it, and exposes a running daily total.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| usage_metadata | {prompt_token_count, candidates_token_count} | each Gemini response | yes |
| model | string | LLM client | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| prompt_tokens / completion_tokens | int | `questions` row |
| cost_usd | float | `questions` row + SSE final event |
| daily_total_usd | float | `GET /cost/today` + SSE final event |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (none — local computation) | tokens × per-model rate | if usage_metadata absent, record 0 tokens and a `cost_estimated:false` flag; never block the answer |

## Business Rules
- Per-question cost = sum over its LLM calls (code-gen + summarise, + retry if any) of `tokens × rate`. Rates per model in `src/llm/pricing.py` (`gemini-2.5-flash` input/output per 1K tokens).
- Daily total = sum of `cost_usd` for `questions` created on the server-local current date.
- Cost is shown per question ("This question: N tokens · ~$X") and as a running daily total ("Today: $Y") in the UI.
- Default model is the cheap tier; the system makes exactly two LLM calls per question (plus at most one retry).

## Success Criteria
- [ ] After a question, `questions.prompt_tokens`/`completion_tokens`/`cost_usd` are non-null and consistent with the rates.
- [ ] `GET /cost/today` returns the sum of today's question costs; asking a second question increases it.
- [ ] The UI shows both the per-question cost and the daily total.
- [ ] A missing `usage_metadata` does not break the answer (cost recorded as 0/estimated, answer still returned).
