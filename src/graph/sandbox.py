"""Pandas eval sandbox for `execute_action`.

The agent's single "tool" is eval/exec of a pandas expression the model emits as
text. This module builds the fixed namespace that expression runs in and the safe
`eval_expression` helper that captures the result, any Plotly figure, and any error.

Per `spec/agent.md` -> "## Tools & Tool Calling":
- Namespace: `df` (first DataFrame), `df1`/`df2`/... per dataset (ordered by
  `dataset_ids`), a `<filename_stem>` alias per dataset, plus the libraries
  `pd, np, px, go, plt, sns, scipy, stats, sklearn, sm`, plus `save_dataset`.
- No filesystem/network builtins beyond these are exposed.

Phase 2 scope: `save_dataset` is a STUB that returns a confirmation string WITHOUT
writing files (full derived-dataset persistence lands in Phase 4). Chart capture is
wired here even though the UI renders charts in Phase 4 — it must never crash.
"""
from __future__ import annotations

import re
import traceback
from typing import Any

import numpy as np
import pandas as pd

# Heavier optional libs imported lazily-ish at module load so the namespace is
# complete; all are guaranteed present by pyproject.
import plotly.express as px
import plotly.graph_objects as go
import matplotlib

matplotlib.use("Agg")  # headless: never try to open a window in the sandbox
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402
import scipy  # noqa: E402
from scipy import stats  # noqa: E402
import sklearn  # noqa: E402
import statsmodels.api as sm  # noqa: E402


_IDENTIFIER_RE = re.compile(r"[^0-9a-zA-Z_]")


def _safe_alias(stem: str) -> str | None:
    """Turn a filename stem into a valid python identifier alias, or None."""
    alias = _IDENTIFIER_RE.sub("_", stem).strip("_")
    if not alias or alias[0].isdigit():
        alias = f"_{alias}" if alias else ""
    return alias or None


def save_dataset(df: Any, name: str, desc: str = "") -> str:
    """Phase 2 STUB for the derived-dataset tool.

    The FULL implementation (writes CSV+Parquet, registers a `datasets` row with
    derivation lineage) lands in Phase 4. Here we only validate the input and
    return a confirmation string so a model that calls it does not crash the run.
    """
    try:
        n_rows = int(getattr(df, "shape", (0,))[0]) if hasattr(df, "shape") else "?"
    except Exception:
        n_rows = "?"
    return (
        f"save_dataset('{name}'): noted ({n_rows} rows). "
        "Derived-dataset persistence lands in Phase 4 — nothing written yet."
    )


def build_namespace(
    dataframes: list[pd.DataFrame],
    filenames: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the eval namespace for a run.

    `dataframes` are ordered by `dataset_ids`. `filenames` (same order, optional)
    provide the `<filename_stem>` aliases.
    """
    ns: dict[str, Any] = {
        "pd": pd,
        "np": np,
        "px": px,
        "go": go,
        "plt": plt,
        "sns": sns,
        "scipy": scipy,
        "stats": stats,
        "sklearn": sklearn,
        "sm": sm,
        "save_dataset": save_dataset,
    }

    filenames = filenames or []
    for idx, frame in enumerate(dataframes):
        # df1 / df2 / ... (1-based) per dataset
        ns[f"df{idx + 1}"] = frame
        # <filename_stem> alias when we have a usable name
        if idx < len(filenames) and filenames[idx]:
            stem = filenames[idx].rsplit(".", 1)[0]
            stem = stem.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            alias = _safe_alias(stem)
            if alias and alias not in ns:
                ns[alias] = frame

    # `df` is the first DataFrame (most questions are single-dataset)
    if dataframes:
        ns["df"] = dataframes[0]

    return ns


def _capture_charts(result: Any) -> list[str]:
    """If the eval result is a Plotly figure (or list of them), serialise to JSON.

    A failed serialisation is swallowed — chart capture must never abort a run.
    """
    charts: list[str] = []
    candidates = result if isinstance(result, (list, tuple)) else [result]
    for item in candidates:
        if isinstance(item, go.Figure):
            try:
                charts.append(item.to_json())
            except Exception:
                pass
    return charts


def _stringify(result: Any) -> str:
    """Convert an arbitrary eval result to a readable string for the transcript."""
    if result is None:
        return "None"
    if isinstance(result, go.Figure):
        return "[Plotly figure captured]"
    try:
        if isinstance(result, (pd.DataFrame, pd.Series)):
            return result.to_string()
    except Exception:
        pass
    text = str(result)
    # Keep the transcript from exploding on huge frames; the model only needs a view.
    if len(text) > 6000:
        text = text[:6000] + "\n... [truncated]"
    return text


def eval_expression(
    expr: str, namespace: dict[str, Any]
) -> tuple[str, list[str], bool, str | None]:
    """Evaluate `expr` in `namespace`, capturing result, charts, error.

    Returns `(result_str, charts_json_list, is_error, error_str)`.

    Tries `eval` first (expressions, the common case); on a `SyntaxError` falls
    back to `exec` (statements, e.g. multi-line assignments) and reports the value
    of a trailing `_` / last expression where possible. Any exception is caught and
    reported — execution errors are recoverable (the graph loops back to plan).
    """
    expr = (expr or "").strip()
    if not expr:
        return "", [], True, "empty expression"

    try:
        try:
            result = eval(expr, namespace)  # noqa: S307 — sandboxed, intentional
        except SyntaxError:
            # Statement(s) rather than a single expression: exec, then surface the
            # value of the last bare expression if the model left one on its own line.
            exec(expr, namespace)  # noqa: S102 — sandboxed, intentional
            last = expr.strip().splitlines()[-1].strip()
            try:
                result = eval(last, namespace)  # noqa: S307
            except Exception:
                result = "[executed statements; no return value]"

        charts = _capture_charts(result)
        return _stringify(result), charts, False, None
    except Exception as exc:  # noqa: BLE001 — recoverable, recorded in transcript
        err = f"{type(exc).__name__}: {exc}"
        # One compact traceback line helps the model self-correct.
        tb = traceback.format_exc().strip().splitlines()
        if tb:
            err = f"{err}\n{tb[-1]}"
        return "", [], True, err
