import re


class SqlNotAllowed(Exception):
    """Raised when a SQL string is not a single read-only SELECT/WITH statement."""


_FORBIDDEN = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "ATTACH",
    "DETACH",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "GRANT",
}


def _strip_comments(sql: str) -> str:
    # Remove /* block */ comments.
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove -- line comments.
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def assert_read_only(sql: str) -> str:
    """Return the cleaned SQL if it is a single read-only SELECT/WITH...SELECT
    statement. Raise SqlNotAllowed otherwise."""
    if sql is None or not sql.strip():
        raise SqlNotAllowed("Empty SQL is not allowed.")

    cleaned = _strip_comments(sql).strip()

    # Reject multiple statements: more than one non-empty statement after splitting on ;.
    statements = [s for s in cleaned.split(";") if s.strip()]
    if len(statements) != 1:
        raise SqlNotAllowed(
            f"Only a single statement is allowed (found {len(statements)})."
        )

    statement = statements[0].strip()

    # Token-level forbidden-keyword check (word boundary, case-insensitive).
    upper = statement.upper()
    tokens = set(re.findall(r"[A-Z_]+", upper))
    forbidden = tokens & _FORBIDDEN
    if forbidden:
        raise SqlNotAllowed(
            f"Forbidden keyword(s) not allowed in read-only query: {sorted(forbidden)}"
        )

    # Must start with SELECT or WITH.
    first = re.match(r"\s*([A-Za-z]+)", statement)
    head = first.group(1).upper() if first else ""
    if head not in ("SELECT", "WITH"):
        raise SqlNotAllowed("Only SELECT or WITH...SELECT statements are allowed.")

    # A WITH must resolve to a SELECT (no DML in the body — already covered by the
    # forbidden-keyword set, but require a SELECT to be present).
    if head == "WITH" and not re.search(r"\bSELECT\b", upper):
        raise SqlNotAllowed("A WITH statement must resolve to a SELECT.")

    return statement
