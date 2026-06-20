# Capability: Data Analysis  ·  Priority: P1

## What & why
A user uploads a CSV or JSON dataset and asks an analytical question in plain English. The agent
inspects the schema with `inspect_data`, executes a safe pandas expression with `execute_pandas`,
and returns a grounded answer with the exact computed result — never an invented number. For
chart-able results (time series, comparisons) the answer also includes a Chart.js config that the
browser renders as an interactive bar or line chart. The dataset is retained in the session so
follow-up questions require no re-upload. This is the v1 real slice — it calls the runtime LLM
and is proven live by the outcome eval.

## Acceptance criteria (EARS — these ARE the eval inputs)

- WHEN the user uploads a CSV dataset and asks an aggregate question the system SHALL execute a pandas expression and return the correct numeric result grounded in the data. [@eval: tests/test_data_analyst_gate.py::test_csv_aggregate]
- WHILE a dataset is loaded in the session WHEN the user asks a follow-up analytical question the system SHALL answer from the retained dataset without re-upload. [@eval: tests/test_data_analyst_gate.py::test_followup_retains_dataset]
- IF the pandas expression contains filesystem or shell operations THEN the system SHALL reject it and explain why. [@eval: tests/test_data_analyst_gate.py::test_rejects_unsafe_code]

## Targets (code files this capability governs — reconciliation anchor)
targets: agent/tools.py, agent/sessions.py, agent/runner.py, agent/graph.py, agent/guardrails.py, agent/state.py

## Tools & layers touched
- tool: inspect_data  (in-process @tool — reads session DataFrame: shape, dtypes, head(3), null counts)
- tool: write_todos  (in-process @tool — records the planning scratchpad before multi-step work)
- tool: execute_pandas  (in-process @tool — safe_eval validates AST then evaluates pandas expression)
- tool: finish  (in-process @tool — returns answer text + optional Chart.js config JSON; chart extracted by finalize_node into AgentState.chart)
- layers: Memory (short-term) ON — DataFrame stored in SessionResources.by_id["df"], persists across turns in the same session; released only on explicit session delete

## Evaluation
- outcome evaluation_steps:
  - PRIMARY: the question asks for the total revenue. The dataset has 12 months of revenue summing to 767,000. Does the answer state 767,000 (or equivalent, e.g. $767,000 or 767000)? Score 5 if correct, 0 if wrong or missing.
  - Is the answer grounded in the data (uses execute_pandas result) rather than invented? Score 5 if clearly computed, 0 if the number is guessed.
- expect_tools: [inspect_data, execute_pandas]
- forbid_tools: []
