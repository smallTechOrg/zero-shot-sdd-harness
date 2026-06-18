"""Action-safety boundary for model-generated SQL (patterns/react-agent.md).

Model output is untrusted. Before any query runs against DuckDB it is parsed (sqlglot,
never regex) and rejected unless it is a single read-only SELECT/WITH statement. A
rejection is returned as a value the ReAct loop can observe and self-correct on — never
an exception that crashes the run.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

# Top-level statement types that read data. Anything else is rejected.
_ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Subquery)

# Expression types that mutate or escape the read-only sandbox.
_BLOCKED_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,  # ATTACH, COPY, INSTALL, LOAD, PRAGMA, EXPORT, CALL, SET, etc.
    exp.Merge,
)


class SqlSafetyError(ValueError):
    """Raised internally; callers convert to a recoverable action-history error value."""


def validate_read_only(sql: str) -> str:
    """Return the validated SQL, or raise SqlSafetyError with a model-readable reason."""
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise SqlSafetyError("Empty query.")

    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except Exception as exc:
        raise SqlSafetyError(f"Could not parse SQL: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlSafetyError(
            "Only a single SELECT statement is allowed (no multiple statements)."
        )

    root = statements[0]

    # A WITH … SELECT parses as a Select with a `with` arg — both are fine.
    if not isinstance(root, _ALLOWED_ROOTS):
        raise SqlSafetyError(
            f"Only read-only SELECT queries are allowed; got '{root.key.upper()}'."
        )

    for node in root.walk():
        if isinstance(node, _BLOCKED_TYPES):
            raise SqlSafetyError(
                f"Statement type '{node.key.upper()}' is not allowed — read-only SELECT only."
            )

    return sql
