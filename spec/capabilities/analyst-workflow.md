# Capability: Analyst Workflow Simulation  ·  Priority: P3

## What & why
After answering a question, the agent proactively surfaces three analyst-grade follow-up insights
the user did not ask for (e.g. anomalies, trend observations, suggested next questions). This
simulates the workflow of a senior data analyst who doesn't just answer but guides the investigation.
**Stub until promoted:** returns the sentinel string `ANALYST_WORKFLOW_STUB`.

## Acceptance criteria (EARS — these ARE the eval inputs)

- WHEN the user receives an analytical answer the system SHALL append at least three proactive analyst insights as a stub. [@eval: tests/test_analyst_workflow_gate.py::test_analyst_workflow_stub]

## Targets (code files this capability governs — reconciliation anchor)
targets: agent/runner.py, agent/tools.py

## Tools & layers touched
- layers: stub — returns sentinel until promoted

## Evaluation
- outcome evaluation_steps:
  - Does the response contain the sentinel string ANALYST_WORKFLOW_STUB? Score 5 if yes, 0 if no.
- expect_tools: []
- forbid_tools: []
