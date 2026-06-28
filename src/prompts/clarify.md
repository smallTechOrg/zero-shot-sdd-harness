The CLARIFY step does not call the LLM — the clarifying question is drafted by
the PLAN node and simply surfaced to the user. This prompt file documents the
clarify checkpoint for completeness.

When the PLAN node sets needs_clarification, the run ends with status
"needs_clarification" and the clarifying_question is returned as the run's
answer. The user replies as a new turn (human-in-the-loop checkpoint).
