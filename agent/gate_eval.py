import argparse
import asyncio
import sys
from sqlalchemy import select
from .db import get_sessionmaker, Run
from .evals import stable_outcome_eval, trajectory_eval

CRITERION = "WHEN the user uploads a CSV dataset and asks an aggregate question the system SHALL execute a pandas expression and return the correct numeric result grounded in the data."
EVALUATION_STEPS = [
    "PRIMARY: the question asks for the total revenue. The dataset has 12 months of revenue summing to 767,000. Does the answer state 767,000 (or equivalent, e.g. $767,000 or 767000)? Score 5 if correct, 0 if wrong or missing.",
    "Is the answer grounded in the data (uses execute_pandas result) rather than invented? Score 5 if clearly computed, 0 if the number is guessed.",
]
EXPECT_TOOLS = ["inspect_data", "execute_pandas"]
FORBID_TOOLS = []

SAMPLES, THRESHOLD, MARGIN = 5, 3, 0.5


async def main(run_id: str, goal: str) -> int:
    async with get_sessionmaker()() as s:
        run = (await s.execute(select(Run).where(Run.id == run_id))).scalar_one()
    outcome_ok, mean, detail = await stable_outcome_eval(
        goal, run.answer, CRITERION, EVALUATION_STEPS,
        threshold=THRESHOLD, samples=SAMPLES, margin=MARGIN)
    ok_t, reasons = await trajectory_eval(run_id, expect_tools=EXPECT_TOOLS, forbid_tools=FORBID_TOOLS)
    print(f"OUTCOME scores={detail['scores']} mean={mean:.2f} spread={detail['spread']} "
          f"(need mean>={THRESHOLD - MARGIN})", file=sys.stderr)
    if not outcome_ok:
        print("OUTCOME FAIL: below threshold-with-margin or unstable", file=sys.stderr)
    if not ok_t:
        print(f"TRAJECTORY advisory (not blocking until a 2nd capability): {reasons}", file=sys.stderr)
    return 0 if outcome_ok else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--goal", required=True)
    a = p.parse_args()
    sys.exit(asyncio.run(main(a.run_id, a.goal)))
