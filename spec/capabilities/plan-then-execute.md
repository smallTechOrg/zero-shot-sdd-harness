# Capability: Plan-then-Execute Deep Analysis (Phase 4 — stub in Phase 1)

## What It Does
For complex questions a single pass cannot answer, the agent plans multi-step, executes each step, reflects on intermediate results, and iterates up to a bounded step count until the answer holds — escalating to a stronger model only when stuck.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| dataset_id, question | as base | ask body | yes |
| deep_mode | bool | UI toggle (real in Phase 4; labelled stub in Phase 1) | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| plan + step trace | [{step, code, result, reflection}] | SSE + `questions` row |
| final answer | as [answer-question-with-code](answer-question-with-code.md) | SSE final event |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini (flash, escalate to pro when stuck) | plan, generate, reflect | bounded `max_steps` halts the loop; returns best result + "what I tried" |
| Sandbox / DuckDB executor | run each step (pandas or SQL via router) | per-step retry, then halt |

## Business Rules
- Patterns #6 Planning + #4 Reflection + #11 Goal Monitoring + #16 escalation + #2 routing (pandas vs SQL). Reached for only on a concrete need — NOT Phase 1.
- The loop is bounded by `max_steps`; it never runs unbounded.
- Privacy + sandbox guarantees are unchanged: still schema-only to the LLM, still sandboxed execution.

## Success Criteria
- [ ] A multi-step question a single pass gets wrong is answered correctly by the bounded loop, which then stops.
- [ ] The plan/step trace renders in the UI deep-mode view.
- [ ] Escalation to `gemini-2.5-pro` happens only when the flash loop is stuck, and is reflected in cost.
