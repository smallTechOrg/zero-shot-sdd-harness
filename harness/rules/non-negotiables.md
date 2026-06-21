# Non-Negotiables

These rules are never optional and must survive context compression. If you can remember
only a few rules, remember these.

1. **Humans own the goal.** No code is written until the spec is complete enough to act
   and the supervisor has reviewed it (with researcher, engineer feasibility, reviewer
   testability). Elicit as much as needed — the loop catches the rest.

2. **Spec before code.** No change to `src/` without a backing change in `spec/`. If
   asked to build something not in the spec: stop, name the gap, spec it, get sign-off,
   then build. (See `spec-driven.md`.)

3. **Outcome is evidence.** Never claim a test passed without running it. "It should
   work" is not a result. Show the output, or say you couldn't run it.

4. **Docs must be true.** Every command in the README and docs must work exactly as
   written, from the directory stated. Test them before marking work done. A README that
   lies is worse than no README.

5. **Commit then push — always.** `git commit` and `git push` are one indivisible
   action. A commit that is not pushed does not exist. (Enforced by a hook; see
   `git-and-delivery.md`.)

6. **Never `git add -A` / `git add .`** — stage specific files. Bulk staging sweeps in
   stray files from prior work and poisons the commit.

7. **All code lives on a feature branch and reaches `main` only via a reviewed
   PR.** Open the PR before the first feature-branch commit. (See `git-and-delivery.md`.)

8. **One phase at a time.** Never start phase N+1 while phase N is failing. Each phase
   runs end-to-end and passes its gate first. (See `../process/lifecycle.md`.)

9. **The loop must close before you stop.** Before ending any unit of work: spec ↔ src ↔
   logs reconcile, tests pass, the tree is clean, the branch is pushed, and the session
   report in `logs/sessions/` is up to date.

10. **Generate only what is needed.** Build what the spec says, nothing more. Note future
    ideas in the session report and move on.
