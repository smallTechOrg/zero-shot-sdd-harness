"""Sandboxed pandas executor (privacy + safety core).

Runs LLM-generated pandas code against the FULL in-memory DataFrame in a
restricted namespace:

- AST allow-list rejects imports and dangerous attribute/name access
  (``os``/``sys``/``subprocess``/``open``/``eval``/``exec``/dunder escapes).
- ``__builtins__`` is replaced with a curated safe subset.
- The code MUST assign its answer to ``result``.
- Only a COMPACT aggregate summary of ``result`` is returned — never a slice
  of raw input rows. User-code errors are CAPTURED into ``error``, never raised.
"""
from __future__ import annotations

import ast
import io
from contextlib import redirect_stdout
from typing import Any

import numpy as np
import pandas as pd

# Names that may never be referenced (Load/Store) in generated code.
_FORBIDDEN_NAMES = frozenset(
    {
        "os", "sys", "subprocess", "open", "eval", "exec", "compile",
        "__import__", "__builtins__", "globals", "locals", "vars",
        "input", "exit", "quit", "breakpoint", "memoryview",
        "getattr", "setattr", "delattr",
    }
)

# Attribute names that smell like a sandbox escape.
_FORBIDDEN_ATTR_PREFIXES = ("__",)
_FORBIDDEN_ATTRS = frozenset(
    {"system", "popen", "fork", "spawn", "remove", "unlink", "rmdir"}
)

# Curated safe builtins exposed to generated code.
_SAFE_BUILTINS = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in (
        "abs", "min", "max", "sum", "len", "round", "sorted", "range",
        "list", "dict", "set", "tuple", "str", "int", "float", "bool",
        "enumerate", "zip", "map", "filter", "any", "all", "print",
        "True", "False", "None",
    )
    if (isinstance(__builtins__, dict) and name in __builtins__)
    or hasattr(__builtins__, name)
}

# Cap how much of an aggregate result we summarise (privacy: never echo a large
# slice of raw input back to the agent / LLM).
_MAX_SUMMARY_ROWS = 50


class _Validator(ast.NodeVisitor):
    """Raises ValueError on any disallowed AST construct."""

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        raise ValueError("imports are not allowed")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        raise ValueError("imports are not allowed")

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"use of '{node.id}' is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        attr = node.attr
        if attr.startswith(_FORBIDDEN_ATTR_PREFIXES) or attr in _FORBIDDEN_ATTRS:
            raise ValueError(f"attribute access to '{attr}' is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        # Block getattr/eval/exec style calls early (also caught by Name).
        if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_NAMES:
            raise ValueError(f"call to '{node.func.id}' is not allowed")
        self.generic_visit(node)


def _validate(code: str) -> None:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"syntax error: {exc}") from exc
    _Validator().visit(tree)


def run(code: str, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Execute ``code`` against ``frames`` and return a privacy-safe result.

    Returns ``{"result_repr", "summary", "stdout", "error"}``. On any user-code
    failure (validation or runtime) ``error`` is set and the rest are empty —
    the exception is NEVER propagated to the caller.
    """
    out: dict[str, Any] = {"result_repr": "", "summary": None, "stdout": "", "error": None}

    try:
        _validate(code)
    except ValueError as exc:
        out["error"] = f"unsafe code rejected: {exc}"
        return out

    namespace: dict[str, Any] = {
        "pd": pd,
        "np": np,
        "__builtins__": _SAFE_BUILTINS,
    }
    namespace.update(frames)

    stdout_buf = io.StringIO()
    try:
        with redirect_stdout(stdout_buf):
            exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
    except Exception as exc:  # user-code error — captured, NOT raised
        out["stdout"] = stdout_buf.getvalue()
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    out["stdout"] = stdout_buf.getvalue()

    if "result" not in namespace:
        out["error"] = "code did not assign to `result`"
        return out

    result = namespace["result"]
    out["result_repr"] = _safe_repr(result)
    out["summary"] = summarize(result)
    return out


def _safe_repr(result: Any) -> str:
    try:
        text = repr(result)
    except Exception:  # pragma: no cover - defensive
        return f"<{type(result).__name__}>"
    return text[:2000]


def summarize(result: Any) -> dict[str, Any]:
    """Build a COMPACT aggregate summary of an execution result.

    For DataFrames/Series only the head (capped) plus shape/columns is captured —
    these are computed/aggregate outputs (e.g. a groupby), capped in size so a
    large raw slice can never be forwarded. Scalars are captured directly.
    """
    if isinstance(result, pd.DataFrame):
        head = result.head(_MAX_SUMMARY_ROWS)
        return {
            "kind": "dataframe",
            "shape": [int(result.shape[0]), int(result.shape[1])],
            "columns": [str(c) for c in result.columns],
            "index_name": _name(result.index.name),
            "rows": _records(head),
            "truncated": bool(result.shape[0] > _MAX_SUMMARY_ROWS),
        }
    if isinstance(result, pd.Series):
        head = result.head(_MAX_SUMMARY_ROWS)
        return {
            "kind": "series",
            "name": _name(result.name),
            "length": int(result.shape[0]),
            "index_name": _name(result.index.name),
            "items": [
                {"index": _json(idx), "value": _json(val)}
                for idx, val in head.items()
            ],
            "truncated": bool(result.shape[0] > _MAX_SUMMARY_ROWS),
        }
    if isinstance(result, (np.generic,)):
        return {"kind": "scalar", "value": _json(result)}
    if isinstance(result, (int, float, str, bool)) or result is None:
        return {"kind": "scalar", "value": result}
    if isinstance(result, dict):
        return {"kind": "dict", "value": {str(k): _json(v) for k, v in list(result.items())[:_MAX_SUMMARY_ROWS]}}
    if isinstance(result, (list, tuple)):
        return {"kind": "list", "value": [_json(v) for v in list(result)[:_MAX_SUMMARY_ROWS]]}
    return {"kind": "other", "value": str(result)[:1000]}


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for _, row in df.iterrows():
        records.append({str(c): _json(row[c]) for c in df.columns})
    return records


def _name(value: Any) -> Any:
    return None if value is None else str(value)


def _json(value: Any) -> Any:
    """Coerce a value to a JSON-safe scalar."""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return f
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (int, float, str, bool)):
        return value
    if pd.isna(value) if not isinstance(value, (list, tuple, dict)) else False:
        return None
    return str(value)
