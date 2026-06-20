# Capability: Multi-Dataset Query  ·  Priority: P2

## What & why
A user can upload and name multiple datasets in one session (e.g. "sales" + "inventory") and ask
questions that span them. The agent registers each dataset by name, uses DuckDB in-process SQL to
cross-join or union them, and returns results with provenance noting which datasets were used.
Serves the "store and organise multiple datasets" success criterion. **Stub until promoted:** returns
the sentinel string `MULTI_DATASET_STUB` so the journey stays green and the capability is registered.

## Acceptance criteria (EARS — these ARE the eval inputs)

- WHEN the user uploads a second named dataset the system SHALL register it and confirm both datasets are available for cross-dataset queries. [@eval: tests/test_multi_dataset_gate.py::test_multi_dataset_stub]

## Targets (code files this capability governs — reconciliation anchor)
targets: agent/tools.py, agent/sessions.py

## Tools & layers touched
- tool: inspect_data  (extended to list all named datasets)
- layers: stub — returns sentinel until promoted

## Evaluation
- outcome evaluation_steps:
  - Does the response contain the sentinel string MULTI_DATASET_STUB? Score 5 if yes, 0 if no.
- expect_tools: []
- forbid_tools: []
