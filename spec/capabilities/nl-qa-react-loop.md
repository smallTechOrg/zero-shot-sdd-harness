# Capability: NL Q&A ReAct Loop (C2)

## What It Does
Answers a plain-English question about a dataset by running a LangGraph ReAct loop that reasons, executes pandas, and iterates until it produces a confident `FINAL ANSWER:`.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | string | `/ask` body | yes |
| dataset_id / dataset_ids | string / list | `/ask` body | yes (one of) |
| session_id | string | `/ask` body | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer_markdown / answer_html | string | `/ask` response + `query_runs.answer` |
| steps | list | `/ask` response + `query_runs.action_history` |
| iteration_count, tokens_* | int | `query_runs` row |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| LLM (Gemini/stub) via `LLMClient` | reason → next pandas action or FINAL ANSWER | recoverable error → retry plan; fatal → handle_error |
| pandas sandbox | eval the action | record step error → loop back to plan |

## Business Rules
- Termination on case-insensitive `FINAL ANSWER:` substring (tolerate preamble).
- `MAX_ITERATIONS` = `AGENT_MAX_ITERATIONS` (default 6); near the cap, force a final answer.
- Execution errors are recoverable (self-correct); 3 consecutive errors or max-iter → force-finalize.
- Full graph spec in `spec/agent.md`.

## Success Criteria
- [ ] An aggregation question ("average of column X") returns a correct numeric answer (verified against real Gemini).
- [ ] A filter/comparison question returns a correct answer.
- [ ] An action that raises is recorded as a step error and the loop self-corrects rather than crashing.
- [ ] The run row is persisted with `status=completed` and a non-empty `answer`.
