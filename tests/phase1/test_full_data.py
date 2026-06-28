"""Full-data execution — the agent runs code on the FULL file, never a sample.

Builds a >=200k-row CSV where the first 1,000 rows give an observably different
aggregate than the whole file, runs a real question, and asserts the answer
matches the FULL-file aggregate.
"""
import json

import numpy as np
import pandas as pd
import pytest

from analysis import profiler
from analysis.dataset_store import get_dataset_store
from db.models import DatasetRow, RunRow
from db.session import create_db_session

N_ROWS = 250_000
SAMPLE = 1_000


def _make_df() -> pd.DataFrame:
    # First 1,000 rows: amount = 1. Remaining ~249k rows: amount = 1000.
    # Sample(first 1k) mean = 1; full mean ~= 996 — wildly different.
    amount = np.empty(N_ROWS, dtype=np.int64)
    amount[:SAMPLE] = 1
    amount[SAMPLE:] = 1000
    return pd.DataFrame({"id": np.arange(N_ROWS), "amount": amount})


@pytest.mark.usefixtures("_require_llm_key")
def test_full_dataset_not_sampled(_isolated_db):
    df = _make_df()
    full_mean = float(df["amount"].mean())
    sample_mean = float(df["amount"].head(SAMPLE).mean())
    # Guard the fixture: full vs sample must be observably different.
    assert abs(full_mean - sample_mean) > 100
    assert full_mean > 900 and sample_mean < 10

    prof = profiler.profile(df)
    with create_db_session() as session:
        ds = DatasetRow(
            name="big.csv",
            file_path="/tmp/big.csv",
            row_count=len(df),
            col_count=df.shape[1],
            profile_json=json.dumps(prof),
            size_bytes=1,
        )
        session.add(ds)
        session.flush()
        dataset_id = ds.id
        run = RunRow(dataset_id=dataset_id, question="What is the average amount?")
        session.add(run)
        session.flush()
        run_id = run.id

    get_dataset_store().put(dataset_id, df)

    from graph.runner import run_to_completion

    result = run_to_completion(
        run_id=run_id,
        dataset_id=dataset_id,
        question="What is the average amount across all rows?",
        profile=prof,
    )

    assert result["status"] == "completed", result
    table = result.get("table")
    assert table is not None, "no results table produced"

    # The computed numeric answer must match the FULL-file mean, not the sample.
    numbers = _extract_numbers(table)
    assert numbers, f"no numeric value in table: {table}"
    assert any(abs(n - full_mean) < 1.0 for n in numbers), (
        f"answer {numbers} does not match full-file mean {full_mean:.2f} "
        f"(sample mean would be {sample_mean})"
    )
    # And it must NOT match the 1k-row sample aggregate.
    assert not any(abs(n - sample_mean) < 1.0 for n in numbers), (
        f"answer {numbers} matches the 1k-row SAMPLE mean {sample_mean} — code ran on a sample"
    )


def _extract_numbers(table: dict) -> list[float]:
    nums: list[float] = []
    for row in table.get("rows", []):
        for cell in row:
            if isinstance(cell, bool):
                continue
            if isinstance(cell, (int, float)):
                nums.append(float(cell))
    return nums
