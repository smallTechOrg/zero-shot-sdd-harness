# UI/UX Standards

The bar every user-facing surface must clear — web, CLI, or chat. `spec/ui.md` says *what* the UI is for this project; this file says *how good it has to be*. If the spec is silent on a question here, this file is the default.

A build that returns 200 but looks broken is a failing build (`rules/ai-agents.md` rule 6). These standards make "looks broken" a concrete, testable thing.

---

## First Principles

**Every state is designed, not just the happy one.** For each view, the four states all exist and are intentional:

1. **Empty** — nothing yet. Explain what this is and the one action to populate it. Never a blank panel.
2. **Loading** — work in progress. Show a skeleton or spinner *with context* ("Generating draft…"), never a frozen screen.
3. **Error** — something failed. Say what failed, why if known, and what the user can do. Never a raw stack trace or a silent no-op.
4. **Ideal / populated** — the designed-for case.

A view that only handles state 4 is half-built.

**The user is never guessing.** At any moment they can answer: Where am I? What can I do here? What just happened? Did it work? If any answer is unclear, the UX is unfinished.

**Feedback is immediate.** Every action acknowledges within ~100ms — a button disables, a row highlights, a toast appears. An action that triggers slow work shows progress, not a dead UI. Nothing the user clicks should feel like it was ignored.

---

## Honesty (raises the bar — and it's a project rule)

- **Stub/offline mode is always visibly labelled.** If the LLM provider is stubbed, every page shows a banner (`rules/ai-agents.md` rule 7). Stub output that looks real is a bug — users will report "it didn't work." Provider auto-selects real when a key is present; the user never flips an extra flag.
- **Never fake progress.** A progress bar reflects real work or it doesn't exist. No spinners over instant operations to feel "busy."
- **Destructive actions confirm.** Delete, overwrite, and irreversible actions ask first and name what will be lost.

---

## Visual & Interaction Quality

- **Hierarchy.** Size, weight, and spacing make the primary action obvious. One clear primary action per view; secondary actions are visibly secondary.
- **Consistency.** One spacing scale, one type scale, one colour system, one set of component patterns. A button looks like a button everywhere. Reuse components — don't reinvent a card per screen.
- **Whitespace is structure**, not waste. Group related things; separate unrelated things. Cramped UIs read as broken.
- **Legibility.** Body text ≥16px (web), comfortable line length (~60–75 chars), real contrast (WCAG AA: 4.5:1 for text). Never grey-on-grey.
- **Responsive / fluid.** The layout survives a narrow window and a wide one. Nothing is clipped, nothing overflows, no horizontal scroll on the primary flow.

---

## Accessibility (table stakes, not a phase)

- Every interactive element is **keyboard reachable** and shows a visible focus ring. Tab order follows reading order.
- Semantic markup: real `<button>`, `<nav>`, `<main>`, `<label>`-linked inputs — not `<div onclick>`. Screen readers and tests both depend on it.
- Images and icon-buttons have text alternatives. Form errors are announced, not just colour-coded (colour is never the *only* signal).
- Respects `prefers-reduced-motion`; animation is never required to understand state.

---

## Copy

- **Plain, specific, human.** "Couldn't reach the database — retrying" beats "Error 500." Error messages name the cause and the next step.
- **Labels are verbs for actions** ("Generate draft"), **nouns for things**. No "Submit" when "Save changes" is truer.
- Empty states and tooltips teach the feature in one line. No lorem ipsum ships.

---

## CLI / Chat Surfaces (the same bar, different shape)

- **CLI:** `--help` is complete and accurate; errors go to stderr with a non-zero exit; long operations stream progress; output is greppable (and `--json` where a machine might consume it). Colour degrades gracefully when piped.
- **Chat:** the agent states what it's doing before a long action and confirms after; it never goes silent mid-task; it surfaces tool failures in plain language; it makes the next step obvious.

---

## Verification

The Phase 2 golden-path smoke test walks the **full primary user journey** and asserts **response content**, not status codes (`rules/ai-agents.md` rule 6, `patterns/phases.md`). Extend it to assert that:

- the empty state renders its guidance copy,
- the stub banner is present when offline,
- an error path renders a human message (not a stack trace).

If you can't write that assertion, the state isn't really designed yet.
