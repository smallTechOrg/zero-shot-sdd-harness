# Capability: Grounded Answer  ·  Priority: P1

## What & why

A user provides a document (a policy, FAQ, notes…) and asks a question in plain English. The agent
retrieves the relevant passages with `search_document` and answers using ONLY the document's content,
quoting the supporting sentence — and refuses to guess when the document doesn't contain the answer. The
document is retained in session-scoped memory, so follow-up questions are answered without re-upload. This
is the v1 real slice — it calls the real runtime LLM and is proven live by the outcome eval.

## Acceptance criteria (EARS — these ARE the eval inputs)

- WHEN the user provides a document and asks a question answerable from it the system SHALL answer with the correct fact, grounded in the document's content. [@eval: tests/test_demo_gate.py::test_demo_gate]
- WHILE a document is loaded in the session WHEN the user asks a follow-up question the system SHALL answer from the retained document without re-upload. [@eval: tests/test_demo_gate.py::test_followup_retains_document]
- WHEN the user shares a durable personal fact the system SHALL remember it and recall it in later sessions. [@eval: tests/test_memory.py::test_long_term_memory_persists]
- IF the model attempts a sensitive or irreversible action THEN the system SHALL require human approval before performing it. [@eval: tests/test_guardrails.py::test_hitl_blocks_risky_without_approval]
- IF the answer contains personal data such as an email THEN the system SHALL mask it before returning. [@eval: tests/test_guardrails.py::test_pii_guardrail_masks_email]

## Tools & layers touched

- tool: `search_document`  (in-process @tool — keyword retrieval over the session document's passages)
- tool: `finish`  (in-process @tool — terminates the loop with the final answer)
- tool: `write_todos`  (in-process @tool — planning scratchpad within the run)
- layers: Retrieval ON (passage retrieval over the provided document)
- layers: Memory (short-term) ON — the session document persists across turns within one `session_id`
- layers: Memory (long-term) ON — durable facts stored via `remember`, recalled across sessions

## Evaluation

- outcome evaluation_steps:
  - Does the answer state a specific fact (not a vague non-answer)?
  - The document states 20 paid vacation days per year — does the answer say 20?
  - Is the answer grounded in the document rather than inventing facts?
- expect_tools: [search_document]
- forbid_tools: []
