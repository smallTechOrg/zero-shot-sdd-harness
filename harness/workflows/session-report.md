# Session Report Template

Copy this template to `reports/sessions/YYYY-MM-DD-HHMMSS-[branch].md` at the start of every session.

---

```markdown
# Session Report — [YYYY-MM-DD HH:MM:SS] — [branch]

## Goal

[What this session is trying to accomplish in one sentence]

## Phase

Phase [N] — [Name]

## Session Start State

- Branch: [branch name]
- Last commit: [short hash and message]
- Tests: [passing / failing / unknown]

---

## Steps Completed

[Log each step as you complete it — do not reconstruct at the end]

- [ ] [step 1]
- [ ] [step 2]

---

## Prompt Log

[Every user message and a one-line summary of your action]

| Time | User Message | Action Taken |
|------|-------------|--------------|
| HH:MM | [message] | [action] |

---

## Decisions Made

[Decisions you made that weren't explicit in the spec or plan — flag these for user review]

---

## Future Improvements

[Things noticed that would be worth doing later — don't do them now]

---

## Session End State

- Branch: [branch name]
- Last commit: [short hash and message]
- Tests: [passing / failing]
- Phase status: [complete / in progress]
- Next steps: [what comes next]
```
