# Capability: Agent Steps Inspector (C23)

## What It Does
Exposes the agent's reasoning steps — each pandas action and its result/error — in a collapsible inspector.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| action_history | list | `/ask` response | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| steps UI | UI | conversation turn |

## External Calls
None.

## Business Rules
- Each step renders a dark code block (the action) + result/error + Copy; a red **Error** badge marks `is_error` steps.
- The inspector is collapsible per turn.

## Success Criteria
- [ ] After a multi-step run, the inspector lists each action with its result.
- [ ] A step that errored shows the red Error badge and the error text.
- [ ] Copy copies the action code.
