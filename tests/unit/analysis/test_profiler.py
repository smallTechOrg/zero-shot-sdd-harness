import json

import numpy as np
import pandas as pd

from analysis.profiler import profile


def _small_df() -> pd.DataFrame:
    # Row 3 duplicates row 0 (fully identical) -> one duplicate row.
    return pd.DataFrame(
        {
            "region": ["North", "South", "West", "North"],
            "amount": [10.5, np.nan, 22.0, 10.5],
            "flag": [True, False, True, True],
            "constant": ["x", "x", "x", "x"],
        }
    )


def test_profile_shape_and_dtypes():
    prof = profile(_small_df())

    assert set(prof.keys()) == {"columns", "quality_flags", "sample_rows"}
    by_name = {c["name"]: c for c in prof["columns"]}

    assert by_name["region"]["dtype"] == "string"
    assert by_name["amount"]["dtype"] == "float64"
    assert by_name["flag"]["dtype"] == "bool"

    # null_count is a plain int.
    assert by_name["amount"]["null_count"] == 1
    assert isinstance(by_name["amount"]["null_count"], int)
    assert by_name["region"]["null_count"] == 0

    # sample_values: up to 3 non-null examples.
    assert 0 < len(by_name["region"]["sample_values"]) <= 3
    assert None not in by_name["amount"]["sample_values"]


def test_profile_quality_flags():
    prof = profile(_small_df())
    flags = " || ".join(prof["quality_flags"])

    assert "amount" in flags and "null" in flags  # null flag present
    assert "duplicate rows" in flags  # the identical row 3
    assert "constant" in flags  # the constant column


def test_profile_is_json_serializable():
    prof = profile(_small_df())
    # Must round-trip through JSON with no numpy types / NaN.
    dumped = json.dumps(prof)
    assert isinstance(dumped, str)

    # NaN in sample_rows becomes None, not float('nan').
    amount_values = [row.get("amount") for row in prof["sample_rows"]]
    assert None in amount_values


def test_profile_empty_dataframe():
    empty = pd.DataFrame({"a": [], "b": []})
    prof = profile(empty)
    json.dumps(prof)  # still serializable
    assert prof["sample_rows"] == []
    assert len(prof["columns"]) == 2
    assert prof["columns"][0]["null_count"] == 0
