# Workflow: Spec Review

A spec review verifies that a code change (or a set of changes) is coherent with the spec
it claims to implement. This is different from a drift audit — it's focused on a specific
change, not the whole repo.

## Trigger

- Any PR or diff that touches `src/` and is gated on spec compliance.
- Any completed implementation phase before it's marked done.
- Explicit request by the user or another agent.

## Procedure

1. **Get the diff.** Work from the current working tree diff against `main` (or a named base branch if specified). Focus on `src/` — config, domain, tools, graph, api.

2. **Map to spec.** For each substantial hunk, identify the spec sentence that authorised it. A spec sentence is a numbered step, a table row, an acceptance criterion, or a named invariant in `spec/`.

3. **Classify each file-level change:**
   - ✅ **Spec'd** — direct implementation of a named spec sentence.
   - ⚠️ **Reasonable inference** — not explicitly spec'd but clearly implied (e.g., a helper function required by a spec'd function).
   - ❌ **Unspec'd** — implements something not mentioned in the spec. Stop; either the spec needs a sentence, or the code should not exist.
   - 🔁 **Spec ahead** — spec calls for something the diff doesn't implement. Note as a gap.

4. **Check invariants.** Did the change uphold the spec's stated invariants (idempotency, uniqueness, failure modes)?

5. **Check public interfaces.** Do any added/changed endpoints, CLI commands, or public function signatures match their spec counterparts exactly (names, types)?

## Report format

```markdown
## Spec review

**Verdict:** Coherent | Minor gaps | Unspec'd code found

**Per-file summary**

| File | Classification | Spec reference |
|---|---|---|
| src/foo/domain/article.py | ✅ Spec'd | capability 03-generate §Behavior step 2 |
| src/foo/api/routes.py | ❌ Unspec'd | no spec sentence for POST /draft |

**Spec gaps** (code doesn't cover all spec)
- capability 03-generate §Behavior step 5: not implemented

**Invariant issues**
- None

**Recommendation**
One sentence.
```

## Constraints

- Read-only. Do not edit files.
- Do not re-spec on the fly. If code needs a spec sentence, say so — don't write the spec sentence.
- Keep the report under 500 words.
