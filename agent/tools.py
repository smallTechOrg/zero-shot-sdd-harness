import re
from langchain_core.tools import tool


@tool
def search_document(query: str) -> str:
    """Search the document provided for this session and return the passages most relevant to the query. Call this to find supporting information before answering."""
    from .sessions import current_session_id, get_session
    sid = current_session_id.get()
    sess = get_session(sid) if sid else None
    chunks = sess.by_id.get("chunks") if sess else None
    if not chunks:
        return "No document is loaded for this session. Ask the user to provide a document first."
    q = set(re.findall(r"\w+", query.lower()))
    scored = sorted(
        ((len(q & set(re.findall(r"\w+", c.lower()))), c) for c in chunks),
        key=lambda x: x[0], reverse=True,
    )
    top = [c for score, c in scored[:3] if score > 0] or [chunks[0]]
    return "\n\n---\n\n".join(top)


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
def finish(answer: str) -> str:
    """Return the final answer to the user and end the run. Call exactly once when done."""
    return answer


TOOLS = [search_document, remember, delete_memories, write_todos, finish]
TOOL_MAP = {t.name: t for t in TOOLS}
FINISH = "finish"
