# Non-Negotiables

These rules are never optional and must survive context compression. If you can remember
only a few rules, remember these.

1. **Humans own the goal.** No code is written until the spec is complete enough to act
   and the supervisor has reviewed it (with researcher, executor feasibility, reviewer
   testability). Elicit as much as needed — the loop catches the rest.

2. **Spec before code.** No change to `src/` without a backing change in `spec/`. If
   asked to build something not in the spec: stop, name the gap, spec it, get sign-off,
   then build. (See `spec-driven.md`.)

3. **Outcome is evidence.** Never claim a test passed without running it. "It should
   work" is not a result. Show the output, or say you couldn't run it.

4. **Docs must be true.** Every command in the README and docs must work exactly as
   written, from the directory stated. Test them before marking work done. A README that
   lies is worse than no README.

5. **Git discipline.** Stage specific files only — never `git add -A`. Commit and push
   are one indivisible action; a commit that is not pushed does not exist. All code
   lives on a feature branch and reaches `main` only via a reviewed PR; open the PR
   before the first feature-branch commit. (See `git-and-delivery.md`.)

6. **One phase at a time.** Never start phase N+1 while phase N is failing. Each phase
   runs end-to-end and passes all four gate requirements before moving on:
   - Tests pass and output is shown in the session report
   - Reviewer has signed off
   - Working tree is clean and pushed
   - Session report is updated with what was done and what is next

7. **The loop must close before you stop.** Before ending any unit of work: spec ↔ src ↔
   logs reconcile, tests pass, the tree is clean, the branch is pushed, and the session
   report in `logs/sessions/` is up to date.

8. **Done means the user says done.** Tests passing and reviewer sign-off are necessary
   but not sufficient. A phase is complete only when the user has explicitly accepted it.
   Never self-declare done.

9. **Never act irreversibly without confirmation.** Deploy, delete, send email, write to
   a production DB, force-push — any action that cannot be undone requires explicit
   approval from the user via the supervisor before proceeding. Timeout is a rejection.

10. **Blockers route to the fix workflow.** If the executor cannot resolve a blocker in
    three attempts, stop immediately, do not hack around it, and route to the fix
    workflow. The analyser diagnoses; the planner re-scopes.

11. **Collect API keys at intake.** Ask for all required API keys before the build begins.
    Never ask mid-build. If a key is missing and was not collected at intake, pause and
    surface to the user — do not continue in a degraded state without telling them.
