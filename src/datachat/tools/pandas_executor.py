"""Sandboxed pandas executor — never evals raw LLM output."""
import re
from typing import Any

import pandas as pd

# Operations the agent may call. Read-only analytics methods only.
_ALLOWED_METHODS = frozenset({
    "describe", "head", "tail", "info",
    "mean", "sum", "min", "max", "median", "std", "var", "count", "nunique",
    "value_counts", "groupby", "sort_values", "nlargest", "nsmallest",
    "corr", "cov", "pivot_table", "crosstab",
    "shape", "dtypes", "columns", "index",
    "isnull", "notnull", "dropna", "fillna",
    "filter", "query", "loc", "iloc",
})

# Parses: df.method() or df["col"].method() or df[["col1","col2"]].method()
_PATTERN = re.compile(
    r'^df(?:\[(?P<cols>[^\]]+)\])?\.(?P<method>\w+)\((?P<args>[^)]*)\)$'
)


def execute(df: pd.DataFrame, action: str) -> tuple[str, bool]:
    """
    Execute a sandboxed pandas action string against df.
    Returns (result_str, is_error).
    """
    action = action.strip()
    m = _PATTERN.match(action)
    if not m:
        return f"Parse error: could not parse action: {action!r}", True

    method_name = m.group("method")
    if method_name not in _ALLOWED_METHODS:
        return f"Safety error: method '{method_name}' is not in the allowed list", True

    cols_raw = m.group("cols")
    args_raw = m.group("args").strip()

    try:
        target = _resolve_target(df, cols_raw)
        result = _call_method(target, method_name, args_raw)
        return _format_result(result), False
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}", True


def _resolve_target(df: pd.DataFrame, cols_raw: str | None) -> Any:
    if cols_raw is None:
        return df
    stripped = cols_raw.strip()
    # ["col1", "col2"] → list selector
    if stripped.startswith("["):
        inner = stripped[1:-1]
        col_list = [c.strip().strip("\"'") for c in inner.split(",") if c.strip()]
        return df[col_list]
    # "col" → single column
    col = stripped.strip("\"'")
    return df[col]


def _call_method(target: Any, method_name: str, args_raw: str) -> Any:
    method = getattr(target, method_name, None)
    if method is None:
        # property access (shape, dtypes, columns)
        return getattr(target, method_name)
    if not args_raw:
        return method()
    # Parse simple args: strings and numbers only, no nested calls
    args = _parse_args(args_raw)
    return method(*args)


def _parse_args(args_raw: str) -> list[Any]:
    """Very conservative arg parser — handles strings, numbers, booleans."""
    result = []
    for part in args_raw.split(","):
        part = part.strip()
        if not part:
            continue
        if (part.startswith('"') and part.endswith('"')) or (part.startswith("'") and part.endswith("'")):
            result.append(part[1:-1])
        elif part == "True":
            result.append(True)
        elif part == "False":
            result.append(False)
        else:
            try:
                result.append(int(part))
            except ValueError:
                try:
                    result.append(float(part))
                except ValueError:
                    result.append(part)
    return result


def _format_result(result: Any) -> str:
    if isinstance(result, pd.DataFrame):
        return result.to_string(max_rows=20)
    if isinstance(result, pd.Series):
        return result.to_string(max_rows=20)
    return str(result)
