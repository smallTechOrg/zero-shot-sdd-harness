# /spec-new-capability

Add a new capability to the spec.

## Usage

```
/spec-new-capability [description of the capability]
```

## Example

```
/spec-new-capability The agent should be able to send a WhatsApp message in addition to email
```

## What It Does

Invokes the spec-writer sub-agent to:
1. Create a new capability file in `spec/capabilities/`
2. Update `spec/capabilities/00-index.md`
3. Check if the capability affects the architecture (`spec/02-architecture.md`) or data model (`spec/04-data-model.md`) and update those if needed

Then invokes the spec-reviewer to validate the new capability fits the existing spec.

## When to Use

- When you have a new requirement that isn't in the current spec
- Before asking the coding agent to implement something new

Never implement a new capability in code without speccing it first. This command is how you do that.
