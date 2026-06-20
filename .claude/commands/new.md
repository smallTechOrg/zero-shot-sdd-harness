---
description: Bootstrap a new app from an idea — spec → v1, one real capability, proven and in sync.
argument-hint: "<app idea>"
---

# /new — bootstrap

Spec → v1. Stand up a new agentic app's thinnest real slice: **one** capability that actually works,
proven, with code as truth and the spec projected from it. The same loop as `/change`, starting from
nothing. The app lives in its **own directory** — never tangled into the harness.

## 1 · Question the idea
Enter plan mode. Interrogate with `AskUserQuestion` until you have: the one user-visible behaviour for v1,
its acceptance check, the runtime model + key, and what's explicitly deferred. Write it as a short spec
(purpose · the one capability · acceptance check · out-of-scope) and get approval before any code.

## 2 · Scaffold the minimum
Create the smallest runnable project that can host the capability — nothing speculative. Pull build
specifics from the `agentic-patterns` skill on demand; pin current library versions (verify first).

## 3 · Implement the one capability (code is truth)
Make it real — real code, a real test bound to the acceptance check. Defer everything else as an explicit,
named stub, never a silent gap.

## 4 · Prove it
Run the `proof-gate` skill: it boots, the capability runs, the answer is right. Not done until green.

## 5 · Project SPEC + review
`spec-projector` writes `spec/` from the code; `reviewer` checks it; then you review. From here on, evolve
it with `/change`.
