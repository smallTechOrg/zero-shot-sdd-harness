import io
from langchain_core.tools import tool


@tool
def inspect_data() -> str:
    """Inspect the loaded dataset: columns, dtypes, shape, and first 3 rows. Always call this first."""
    from .sessions import current_session_id, get_session
    sid = current_session_id.get()
    sess = get_session(sid) if sid else None
    df = sess.by_id.get("df") if sess else None
    if df is None:
        return "No dataset loaded. Ask the user to upload a CSV or JSON file first."
    buf = io.StringIO()
    df.info(buf=buf)
    return (
        f"Shape: {df.shape[0]} rows × {df.shape[1]} columns\n\n"
        f"Columns & dtypes:\n{df.dtypes.to_string()}\n\n"
        f"First 3 rows:\n{df.head(3).to_string(index=False)}\n\n"
        f"Null counts:\n{df.isnull().sum().to_string()}"
    )


@tool
def execute_pandas(code: str) -> str:
    """Execute a single safe pandas expression against the loaded dataset (df).
    Available names: df, pd, np. Returns the result as a formatted string.
    Examples: df['revenue'].sum()  |  df.groupby('month')['revenue'].mean()  |  df.describe()"""
    import numpy as np
    import pandas as pd
    from .sessions import current_session_id, get_session
    from .guardrails import safe_eval
    sid = current_session_id.get()
    sess = get_session(sid) if sid else None
    df = sess.by_id.get("df") if sess else None
    if df is None:
        return "No dataset loaded. Ask the user to upload a CSV or JSON file first."
    try:
        result = safe_eval(code, {"df": df, "pd": pd, "np": np})
    except ValueError as e:
        return f"Code rejected (unsafe): {e}"
    except Exception as e:
        return f"Execution error: {type(e).__name__}: {e}"
    if hasattr(result, "to_string"):
        return result.to_string()
    if isinstance(result, float):
        return f"{result:,.4f}".rstrip("0").rstrip(".")
    if isinstance(result, int):
        return f"{result:,}"
    return str(result)


@tool
async def remember(fact: str) -> str:
    """Store a durable fact about the user or their preferences — recalled in ALL future sessions. Use only when the user explicitly shares something worth remembering long-term."""
    from .memory import remember as _remember
    return f"Remembered: {await _remember(fact)}"


@tool
async def delete_memories() -> str:
    """Permanently delete ALL remembered long-term facts. Sensitive and irreversible — requires human approval (the loop gates this until approved)."""
    from .memory import forget_all
    return f"Deleted {await forget_all()} remembered fact(s)."


@tool
def write_todos(todos: list[str]) -> str:
    """Record a short ordered plan (the planning scratchpad). Call before multi-step work."""
    return "Plan recorded:\n" + "\n".join(f"{i+1}. {t}" for i, t in enumerate(todos))


@tool
def finish(answer: str, chart: str | None = None) -> str:
    """Return the final answer to the user and end the run.
    answer: the text explanation (include a markdown table if tabular).
    chart: optional Chart.js config JSON, e.g.:
      {"type":"bar","data":{"labels":["Jan","Feb"],"datasets":[{"label":"Revenue","data":[45000,38000]}]},"options":{"responsive":true}}
    Only include chart for time-series, comparisons, or distributions — not for scalar answers."""
    return answer


TOOLS = [inspect_data, execute_pandas, remember, delete_memories, write_todos, finish]
TOOL_MAP = {t.name: t for t in TOOLS}
FINISH = "finish"
