# Capability: Dashboard View  ·  Priority: P3

## What & why
A user can request a dashboard — a single response containing multiple charts (e.g. revenue trend +
category breakdown + top-10 table) rendered side-by-side in the browser UI. Serves the "rich
responses in the form of dashboards" success criterion. **Stub until promoted:** returns the sentinel
string `DASHBOARD_STUB` so the journey stays green and the capability is registered.

## Acceptance criteria (EARS — these ARE the eval inputs)

- WHEN the user asks for a dashboard the system SHALL return a multi-chart layout stub. [@eval: tests/test_dashboard_gate.py::test_dashboard_stub]

## Targets (code files this capability governs — reconciliation anchor)
targets: agent/tools.py, agent/server.py

## Tools & layers touched
- tool: finish  (extended with multi-chart payload)
- layers: stub — returns sentinel until promoted

## Evaluation
- outcome evaluation_steps:
  - Does the response contain the sentinel string DASHBOARD_STUB? Score 5 if yes, 0 if no.
- expect_tools: []
- forbid_tools: []
