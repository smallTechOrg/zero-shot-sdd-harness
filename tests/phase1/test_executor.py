"""Sandbox executor — AST allow-list, restricted namespace, error capture.

No LLM needed: these are deterministic unit tests of the code-execution sandbox.
"""
import pandas as pd
import pytest

from analysis import executor


@pytest.fixture
def df():
    return pd.DataFrame(
        {
            "region": ["North", "South", "North", "South", "East"],
            "sales": [100, 200, 300, 400, 500],
        }
    )


def test_valid_pandas_assigning_to_result(df):
    out = executor.run(
        'result = df.groupby("region")["sales"].sum().reset_index()',
        {"df": df},
    )
    assert out["error"] is None
    assert out["summary"]["kind"] == "dataframe"
    # Full-data aggregate: North=100+300=400, South=200+400=600, East=500.
    rows = {r["region"]: r["sales"] for r in out["summary"]["rows"]}
    assert rows == {"North": 400, "South": 600, "East": 500}


def test_scalar_result(df):
    out = executor.run('result = int(df["sales"].sum())', {"df": df})
    assert out["error"] is None
    assert out["summary"] == {"kind": "scalar", "value": 1500}


def test_rejects_import(df):
    out = executor.run("import os\nresult = 1", {"df": df})
    assert out["error"] is not None
    assert "import" in out["error"].lower()


def test_rejects_import_from(df):
    out = executor.run("from os import system\nresult = 1", {"df": df})
    assert out["error"] is not None
    assert "import" in out["error"].lower()


def test_rejects_os_reference(df):
    # os isn't in the namespace, but the allow-list rejects it before execution.
    out = executor.run('result = os.getcwd()', {"df": df})
    assert out["error"] is not None
    assert "os" in out["error"].lower()


def test_rejects_open(df):
    out = executor.run('result = open("/etc/passwd").read()', {"df": df})
    assert out["error"] is not None
    assert "open" in out["error"].lower()


def test_rejects_eval(df):
    out = executor.run('result = eval("1+1")', {"df": df})
    assert out["error"] is not None
    assert "eval" in out["error"].lower()


def test_rejects_dunder_escape(df):
    out = executor.run('result = df.__class__.__mro__', {"df": df})
    assert out["error"] is not None


def test_user_code_error_is_captured_not_raised(df):
    # A KeyError on a missing column must be captured into `error`, never raised.
    out = executor.run('result = df["does_not_exist"].sum()', {"df": df})
    assert out["error"] is not None
    assert "KeyError" in out["error"]
    assert out["summary"] is None


def test_missing_result_assignment_is_an_error(df):
    out = executor.run("x = df.sum()", {"df": df})
    assert out["error"] is not None
    assert "result" in out["error"].lower()
