"""Conditional routing for the analyst graph (see spec/agent.md ## Graph Assembly).

``privacy_guard`` is a single node placed on two passes via the ``phase`` flag:
  * phase == "pre"  (set by ``plan``)         -> route to ``execute_sql``
  * phase == "post" (set by ``execute_sql``)  -> route to ``phrase_answer``

``after_execute`` drives the dialect-safe retry loop: a DuckDB ``sql_error`` with
attempts remaining routes back to ``generate_sql``; once exhausted it routes to
``handle_error``; success routes to ``privacy_guard`` (post-exec, builds aggregate).
"""
from graph.state import MAX_SQL_RETRIES, AnalystState


def after_plan(state: AnalystState) -> str:
    return "handle_error" if state.get("error") else "privacy_guard"


def after_guard(state: AnalystState) -> str:
    if state.get("error"):
        return "handle_error"
    # phase "post" means the aggregate has been built -> phrase; otherwise execute
    if state.get("phase") == "post":
        return "phrase_answer"
    return "execute_sql"


def after_execute(state: AnalystState) -> str:
    if state.get("sql_error"):
        if int(state.get("sql_attempts") or 0) < MAX_SQL_RETRIES:
            return "generate_sql"
        return "handle_error"
    return "privacy_guard"


def after_phrase(state: AnalystState) -> str:
    return "handle_error" if state.get("error") else "pick_chart"
