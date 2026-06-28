# Capability: Stream Answer & Show Code

## What It Does
Streams live step updates and a plain-language answer (built from the result summary) to the browser, and exposes the exact pandas code that ran.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | str | query request | yes |
| result_summary | dict | execute_locally | yes |
| code | str | generate_code | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| SSE step/code/token/done events | event-stream | browser |
| answer | str | `queries.answer` |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | streamed summarize over result_summary | retry/backoff → error event |

## Business Rules
- Summarize receives only the result_summary (aggregates), never raw rows.
- Code is streamed/exposed verbatim with a "rows stayed local" note.
- Token usage emitted in the `done` event.

## Success Criteria
- [ ] The browser receives `step` then streamed `token` events and renders the answer progressively.
- [ ] The `code` event shows the exact pandas executed.
- [ ] The completed query (question, code, answer) is persisted and visible after restart.
