# Capability: Plan & Generate Local Analysis Code

## What It Does
From the user's question and the dataset's schema/profile (never rows), the agent plans an analysis approach and generates runnable pandas code.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | query request | yes |
| schema | dict | DatasetProfile | yes |
| profile | dict | DatasetProfile | yes |
| messages | list | session history (Phase 2) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| plan | str | state + `queries.plan` |
| code | str | state + `queries.code` + SSE `code` event |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | plan (JSON) | retry/backoff → error |
| Gemini | codegen (JSON, `df`→`result`) | retry/backoff → error |

## Business Rules
- LLM payloads contain only schema + profile (+ history). **Never raw rows.**
- Generated code assumes a pre-loaded `df` and assigns the answer to `result`.
- On a sandbox execution error, one repair attempt is allowed (error + code fed back).

## Success Criteria
- [ ] For a "total revenue by month" question, generated code references real column names from the schema.
- [ ] The plan and code are persisted to the `queries` row.
- [ ] No LLM request payload in the run contains raw rows (asserted in test).
