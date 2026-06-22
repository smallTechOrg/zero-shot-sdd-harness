# /spec-check

Run the drift-auditor to check whether the code matches the spec.

## Usage

```
/spec-check
```

## What It Does

Invokes the drift-auditor sub-agent (`.claude/agents/drift-auditor.md`) which:
1. Reads every spec file in `spec/`
2. Searches the codebase for the corresponding implementation
3. Reports any divergences between spec and code

## When to Use

- At the end of each implementation phase (the agent-builder does this automatically)
- After making changes that might have drifted from spec
- Before a PR review
- Any time you're unsure whether the code still matches what the spec says

## Output

Reports CLEAN or DIVERGENCES FOUND, with a table of specific divergences and their severity.
