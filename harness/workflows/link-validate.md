# Workflow: Link Validator

Verify every markdown link in the repo resolves to an existing file (and anchor, when specified).
Broken links are silent documentation rot.

## Scope

All `*.md` files under the repo, excluding `reports/` (plans are ephemeral) and `.git/`.
Relative and anchor-style links only — external `https://` links are **not** checked.

## Procedure

1. **Enumerate markdown files.** Glob `**/*.md` minus the exclusions.
2. **Extract links.** For each file, pull every `[text](target)` where `target` does not start with `http`, `https`, or `mailto:`.
3. **Resolve targets.**
   - Path-only (`foo.md`): check file exists relative to the source.
   - Path + anchor (`foo.md#section`): check file exists AND the anchor matches a heading after slug-conversion (lowercase, spaces→dashes, punctuation stripped).
   - Anchor-only (`#section`): check the anchor exists within the source file's headings.
   - Directory (`foo/`): check the directory exists.
4. **Flag orphans.** Any file under `spec/` not referenced by at least one other markdown file.

## Report format

```
| Source | Link text | Target | Problem |
|---|---|---|---|
| CLAUDE.md:5 | spec/README.md | spec/README.md | missing |
```

Only include rows where `Problem != ok`, plus a final count. Then:

```
## Orphans
- harness/workflows/plan-review.md (0 inbound links)
```

## Constraints

- Read-only.
- URL fragments in link targets are case-sensitive after slug-conversion; be explicit.
- Keep the report under the error count plus 20 lines.
