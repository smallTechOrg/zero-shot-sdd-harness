# Capability: Show Its Work

## What It Does
Surfaces the agent's reasoning for every answer — the plan, the step trace (tried / failed / worked, including any recovered SQL error), the exact DuckDB SQL executed, and the per-question cost — in a collapsible panel, so the user can audit and act on the answer.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| run_id | string | the just-completed ask | yes |
| plan / sql / trace / cost | from QuestionRun | the agent run | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| show-its-work panel | plan + trace + SQL + cost | browser (collapsible) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| (none) | reads the run's persisted plan/sql/trace/cost | if a field is missing, the panel shows what is available |

## Business Rules
- The panel always shows the plan, the trace, and the exact executed SQL — even when the run failed (the trace shows what was tried).
- Recovered SQL errors (a failed attempt then a corrected one) appear in the trace so the recovery is visible.
- Per-question cost is shown (derived from Gemini token usage). The daily total is a Phase-6 stub.
- The panel is collapsed by default; expanding it does not re-run anything.

## Success Criteria
- [ ] After any answer, expanding "show its work" reveals the plan, the step trace, and the exact DuckDB SQL.
- [ ] A run that hit and recovered from a SQL error shows both the failed attempt (with the error) and the corrected one in the trace.
- [ ] A failed run still shows its trace (what was tried) rather than a blank panel.
- [ ] The per-question cost is displayed and is non-zero for a real LLM run.
