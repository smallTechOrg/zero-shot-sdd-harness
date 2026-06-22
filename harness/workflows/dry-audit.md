# Workflow: DRY Audit

Find places where the same fact is stated in more than one file, in violation of the
repo's golden rule: every fact lives in exactly one canonical file; every other mention
is a link.

## Scope

Audit these trees: `spec/` (all files), `harness/` (all files), root files (`README.md`,
`CLAUDE.md`, `.claude/`). Do **not** read `src/` or `tests/` — DRY for code is a separate concern.

## Procedure

1. **Enumerate candidate facts.** Patterns that tend to duplicate:
   - Product identity (purpose statement)
   - Architectural facts (layers, module responsibilities)
   - Library/tooling choices (canonical lib list, pydantic settings)
   - Rule summaries (spec-first, secret hygiene, commit norms)
   - Path/location facts (where secrets live, where plans live)
   - Template structures (capability template)

2. **For each candidate, grep the repo.** Count occurrences outside the declared canonical home. A paraphrase counts — if two files make the same claim, the shorter one should be a link.

3. **Classify each hit:**
   - ✅ **Link** — mentions the fact but links to the canonical home. Fine.
   - ❌ **Restatement** — states the fact in its own words, no link. Violation.
   - ⚠️ **Drift risk** — partial restatement that adds detail; canonical home may need to absorb it.

4. **Cross-check canonical mapping.** Confirm each fact's declared home still matches where it actually lives.

## Report format

```
| Fact | Canonical home | Violations | Recommendation |
|---|---|---|---|
| layered architecture | spec/02-architecture.md | CLAUDE.md:12 (restatement) | Replace with link |
```

End with a one-line summary: violation count, worst offender file.

## Constraints

- Read-only. Do not edit.
- Do not flag the canonical home itself as a duplicate.
- Keep report under 400 words.
