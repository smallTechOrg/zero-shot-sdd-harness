---
description: The change loop — turn one intent into a proven change where code and spec end in sync.
argument-hint: "<what you want to change>"
---

# /change — the loop

Turn one intent into a small, proven change where **code and spec end in sync**. Five steps, in order.

## 1 · Question the intent (before any edit)
Enter **plan mode** — do not edit yet. Read the relevant code, then interrogate the request with
`AskUserQuestion` until it is unambiguous: scope, the one user-visible behaviour, acceptance criteria, what
is explicitly out. Restate it as a 3-line **change brief** (what · acceptance check · out-of-scope) and get
approval to proceed.

## 2 · Implement in CODE (code is truth)
Make the smallest change that satisfies the brief — real code, plus a real test for each acceptance
criterion. No stubs unless the brief says so. Deep how-to (control loop, tools, memory) loads from the
`agentic-patterns` skill on demand — never inline it here.

## 3 · Prove it (verify, don't trust)
Run the **proof-gate** skill: the app boots, the change runs end-to-end, and the acceptance check passes — a
wrong answer fails even on a 200. Not done until it is green. Fix the cause and re-run; never report a pass
you didn't see.

## 4 · Project SPEC from CODE
Hand the diff to the **spec-projector** subagent: it regenerates the affected `spec/` docs *from the new
code*, so the human-readable spec matches reality. You never hand-write the spec.

## 5 · Review
Hand the diff to the **reviewer** subagent (correctness + leanness), surface its findings, then stop for
**your** review. One intent, one reviewable change — that is the tight loop.
