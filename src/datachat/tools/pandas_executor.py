"""
Sandboxed pandas executor using AST validation + restricted eval.

The regex-dispatch approach is too narrow for real pandas: chained calls like
df.groupby("region")["sales"].sum() are the norm, not the exception.
We use ast.parse to validate the expression is safe, then eval it in a
restricted namespace with no builtins.
"""
import ast
from typing import Any

import pandas as pd

# Attribute names that are never permitted regardless of context
_BLOCKED_ATTRS = frozenset({
    "__class__", "__dict__", "__module__", "__qualname__",
    "__subclasses__", "__bases__", "__mro__", "__code__",
    "__globals__", "__closure__", "__builtins__",
    "to_csv", "to_excel", "to_json", "to_sql", "to_pickle",
    "to_clipboard", "to_hdf", "to_feather", "to_parquet",
    "to_stata", "to_gbq", "to_records", "to_dict",
    "pipe",  # can run arbitrary callables
})

# Top-level names allowed in the expression namespace
_ALLOWED_NAMES = frozenset({"df", "pd", "True", "False", "None"})


def _is_safe(tree: ast.Expression) -> tuple[bool, str]:
    """Walk the AST; return (safe, reason) where safe=False means blocked."""
    for node in ast.walk(tree):
        # No imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "import statements not allowed"
        # No exec/eval calls
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("eval", "exec", "compile", "open", "__import__"):
                return False, f"call to {func.id} not allowed"
        # No dunder attributes or blocked names
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr in _BLOCKED_ATTRS:
                return False, f"attribute '{node.attr}' not allowed"
        # Only whitelisted bare names
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_NAMES:
            return False, f"name '{node.id}' not in allowed scope"
    return True, ""


def execute(df: pd.DataFrame, action: str) -> tuple[str, bool]:
    """
    Execute a pandas expression string against df.
    Returns (result_str, is_error).
    """
    action = action.strip()

    # Strip markdown code fences Gemini sometimes adds
    if action.startswith("```"):
        lines = [l for l in action.splitlines() if not l.startswith("```")]
        action = "\n".join(lines).strip()

    try:
        tree = ast.parse(action, mode="eval")
    except SyntaxError as e:
        return f"SyntaxError: {e}", True

    safe, reason = _is_safe(tree)
    if not safe:
        return f"Safety error: {reason}", True

    try:
        result = eval(  # noqa: S307  (safe: restricted namespace, AST-validated)
            compile(tree, "<expr>", "eval"),
            {"__builtins__": {}, "df": df, "pd": pd},
        )
        return _format(result), False
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}", True


def _format(result: Any) -> str:
    if isinstance(result, pd.DataFrame):
        return result.to_string(max_rows=30)
    if isinstance(result, pd.Series):
        return result.to_string(max_rows=30)
    return str(result)
