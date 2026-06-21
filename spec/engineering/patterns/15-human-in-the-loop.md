# Human-in-the-Loop (HITL)

**Category:** Safety & Compliance  
**Status:** Extended

## Intent

Pause agent execution at defined checkpoints to require explicit human approval before the agent takes an irreversible action, makes a high-stakes decision, or operates below a confidence threshold.

## When to use

- Any action that cannot be undone: send email, delete record, make payment, post to social media
- When the agent's confidence in its interpretation or plan is low
- Regulated domains: medical advice, financial decisions, legal actions
- Early deployment of a new agent where the behaviour is not fully trusted
- When user expectations are that "the agent asks before acting" — e.g., a personal assistant

**Do not** require HITL for every action — this defeats the purpose of automation. Gate only what requires it.

## How it works

### Pre-action approval gate

```
Agent generates an execution plan
     │
     ▼
[Identify irreversible actions in the plan]
     │
     ├──(no irreversible actions) ──► execute immediately
     │
     └──(irreversible actions found)
          │
          ▼
     [Pause run, persist state]
     [Send approval request to user: action + parameters + rationale]
          │
          ├──[User approves] ──► resume run from paused state
          │
          └──[User rejects]  ──► cancel run, record reason
```

### Clarification request

```
plan_action
     │
     ├──(intent is ambiguous) ──► ask clarifying question
     │                            ──► wait for response
     │                            ──► resume with clarification in context
     │
     └──(intent is clear) ──► proceed with execution plan
```

### Low-confidence handoff

```
Agent completes draft response
     │
     ├──(confidence score ≥ threshold) ──► return to user directly
     │
     └──(confidence score < threshold)
          │
          ▼
     [Route to human review queue]
     [Human reviews, edits, approves]
          │
          ▼
     Return reviewed response to user
```

## Key components

1. **Action classification** — per-action flag in the tool spec marking it as `requires_approval: true`
2. **State persistence** — paused run state saved to DB (enables long-polling or async resumption)
3. **Notification mechanism** — push notification, email, or in-app alert sent to the approver
4. **Approval API** — `POST /runs/{run_id}/approve` or `/reject` endpoint
5. **Timeout handler** — if approval is not received within N minutes, escalate or auto-cancel

## Variants

| Variant | Description |
|---|---|
| **Pre-flight approval** | Show the entire execution plan before starting execution. User approves the whole plan at once. |
| **Per-action approval** | Pause at each irreversible action individually. Higher safety, higher friction. |
| **Async HITL** | Agent submits an approval request and immediately returns a "pending" response to the user. User approves later. Agent resumes when approved. |
| **Delegated approval** | Agent routes to a supervisor/manager, not the requesting user. For multi-stakeholder workflows. |

## Related patterns

- [14-guardrails.md](14-guardrails.md) — guardrails block before the agent starts; HITL pauses mid-execution
- [13-router.md](13-router.md) — router can route high-stakes queries directly to HITL queue without entering the agent loop
- [02-tool-registry.md](02-tool-registry.md) — `requires_approval` flag is set in the tool's Capability spec
- [19-checkpoint-resume.md](19-checkpoint-resume.md) — HITL relies on state persistence to pause and resume; checkpoint/resume is the implementation mechanism
- [22-observability.md](22-observability.md) — every approval decision must be logged with approver, timestamp, and approved action details

## Implementation notes

- The approval request must show the user exactly what the agent intends to do — tool name, capability, and parameters in human-readable form. "The agent wants to send an email to john@example.com with subject 'Invoice #1234'" is better than a raw JSON dict.
- Every approval decision is immutable audit log material. Store who approved, when, and what parameters were approved. Do not allow post-hoc modification.
- Approval timeouts should have a sensible default (e.g., 24 hours) and be configurable per tool. A time-sensitive action (e.g., travel booking) may need a 1-hour timeout.
- Test the full approval flow in Phase 2 with stubs — the approval API endpoint, the state persistence, and the resumption path are all critical paths that must be tested.
- In multi-user systems, ensure the approval request is routed to the correct user/role, and that other users cannot approve/reject another user's run.
