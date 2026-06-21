# Harness Self-Benchmark

The harness's job is to build agents **fast and high-quality**. You cannot improve what you
don't measure, and the dominant cost of a run is not obvious from the inside. This benchmark
makes both axes measurable so every harness change can be proven a win (or caught as a
regression) instead of guessed.

It is the **dogfood loop made quantitative**: the verbose session reports
([SESSION.md](../process/templates/SESSION.md)) supply the raw numbers; this benchmark turns
them into a comparable score per run.

This directory holds **only the method** — how a run is scored. It does not hold the briefs and
it does not capture results. Briefs live out-of-band (the owner keeps and runs them, sharing
each as the opening message to `/build`); run logs come back to the scorer, who applies the
rubric here.

## What it measures — two axes, never one

A change that makes a run faster but drops quality is a regression, and vice-versa. Every
benchmark run is scored on **both**:

- **Speed** — wall-clock and round-trips (see [rubric.md](rubric.md) → Speed).
- **Quality** — gate-pass, defects, evals, drift (see [rubric.md](rubric.md) → Quality).

A run **passes** only if it clears the quality floor *and* the speed targets. Speed bought by
cutting a quality check does not count.

## Scoring procedure

You score from a **session run log the owner provides** — the brief was run through `/build`
out-of-band, and the resulting session report is handed back here for scoring.

1. Read the session report. Its per-stage start/end timestamps (non-negotiable #12) and Run
   telemetry table supply every number the rubric needs.
2. Score the run against [rubric.md](rubric.md) — speed metrics against their targets, every
   quality-floor item against its pass condition.
3. Record the raw numbers and the verdict in the run's own session report (or share it back to
   the owner). Results are **not** captured in this repo.

To attribute a delta, score the **same brief** before and after a harness change, and change
one variable at a time (e.g. warm recipes OR effort drop, not both) so the difference is real.
Note the harness commit + model/effort alongside the verdict so trends stay attributable.

## Files

- [rubric.md](rubric.md) — the two-axis scoring rubric + pass thresholds
