# Workflow: Scaffold a New Capability Spec

Capabilities are the atomic product units. Each capability spec describes one thing the agent can do.
This workflow scaffolds a new capability file from the standard template.

## Trigger

The user names a new capability (by slug or description). The planner or spec-author invokes this workflow.

## Procedure

1. **Determine the slug.** If the user gave a description rather than a slug, derive a kebab-case slug (≤ 5 words).

2. **Find the next capability file number.** Read `spec/capabilities/index.md` for existing entries. The next file is `NN-<slug>.md` where NN is the next unused two-digit number.

3. **Write the capability file.** Use the template below.

4. **Register in index.** Append a row to the table in `spec/capabilities/index.md`.

5. **Return the path** and a one-sentence summary. Do not implement the capability — that's the planner's job.

## Capability template

```markdown
# Capability: <Name>

**Status:** draft

## Purpose

One sentence. What the agent can do, from the user's perspective.

## Inputs

| Field | Type | Required | Description |
|---|---|---|---|
| | | | |

## Outputs

| Field | Type | Description |
|---|---|---|
| | | |

## Behavior

Numbered steps. Refer to tools, domain models, and agents by their spec'd names.

1. ...
2. ...

## Failure modes

| Condition | Behavior |
|---|---|
| | |

## Acceptance criteria

Checkbox list. Each item must be testable.

- [ ] ...
```

## Constraints

- Do **not** invent requirements. Use only information the user provides plus what's already in `spec/`.
- Leave all tables empty rather than populating from assumptions.
- Mark status as `draft` always.
