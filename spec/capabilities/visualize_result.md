# Capability: Visualize Result

## What It Does
Given a computed result table, automatically selects an appropriate chart type and renders it as an interactive chart (zoom/hover), alongside a summary table — or suggests 2-3 follow-up questions.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| result_table | JSON | output of [answer_question](./answer_question.md) | yes |
| question | string | request | yes |
| profile | JSON | dataset profile | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| chart_spec | JSON ({chart_type, x, y, series, title}) | response + DB ([Turn](../data.md#entity-turn)) |
| follow_ups | list of 2-3 suggested question strings | response + DB |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (LLM) | choose chart type + draft follow-up suggestions from result shape + profile (no raw rows) | partial — fall back to a table-only render, no follow-ups |

## Business Rules
- Chart type is chosen automatically from the result shape (e.g. time series → line, categorical breakdown → bar, two numerics → scatter, single value → big-number/table).
- WHEN the result is not chartable (single scalar or free text), the agent SHALL render a summary table only and still offer follow-ups.
- The chart is rendered client-side from the `chart_spec` + `result_table`; the executor never produces image bytes.
- Follow-up suggestions are derived from the profile + the current answer, not from raw rows.

## Success Criteria
- [ ] A grouped/aggregated result yields a `chart_spec` whose `chart_type` matches the data shape (bar for category counts, line for a date axis).
- [ ] The frontend renders the chart interactively (hover shows values) from the returned spec.
- [ ] Exactly 2-3 follow-up suggestions are returned for a successful answer.
- [ ] A scalar result (e.g. one number) renders as a table/big-number with no broken chart.
