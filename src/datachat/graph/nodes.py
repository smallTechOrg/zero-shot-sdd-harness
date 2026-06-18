"""ReAct agent nodes."""
import json
import pathlib
import re
from typing import Any

import pandas as pd

from datachat.graph.state import AgentState

# DataFrame store keyed by session_id. Persists across questions in the same session.
# Released only when the session is explicitly deleted (release_session) or server restarts.
_dataframe_store: dict[str, pd.DataFrame] = {}

_PROMPT_TEMPLATE = pathlib.Path(__file__).parent.parent / "prompts" / "plan_action.md"


def _load_prompt() -> str:
    return _PROMPT_TEMPLATE.read_text()


def _parse_llm_response(raw: str) -> tuple[str | None, str | None]:
    """
    Parse DESCRIPTION/ACTION block from LLM output.
    Returns (description, action_expr) — either may be None if not found.
    FINAL ANSWER responses are handled by the edge, so not parsed here.
    """
    desc_match = re.search(r"DESCRIPTION:\s*(.+)", raw, re.IGNORECASE)
    action_match = re.search(r"ACTION:\s*(.+)", raw, re.IGNORECASE)
    description = desc_match.group(1).strip() if desc_match else None
    action = action_match.group(1).strip() if action_match else None
    # Strip markdown fences Gemini sometimes wraps around the action
    if action and action.startswith("`"):
        action = action.strip("`").strip()
    return description, action


def setup(state: AgentState) -> AgentState:
    session_id = state["session_id"]
    if session_id not in _dataframe_store:
        return {**state, "error": f"No DataFrame found for session {session_id}"}
    df = _dataframe_store[session_id]
    return {
        **state,
        "df_columns": list(df.columns),
        "action_history": [],
        "iteration_count": 0,
        "tokens_input": 0,
        "tokens_output": 0,
        "final_answer": None,
        "error": None,
    }


def plan_action(state: AgentState) -> AgentState:
    from datachat.llm.client import generate

    history = state.get("action_history", [])
    history_text = (
        "\n".join(
            f"Step {i+1}: {h['description']}\nResult: {h['result']}\n"
            for i, h in enumerate(history)
        )
        if history
        else "(none yet)"
    )

    prompt = _load_prompt().format(
        columns=", ".join(state.get("df_columns", [])),
        question=state.get("question", ""),
        action_history=history_text,
    )

    resp = generate(prompt)
    return {
        **state,
        "llm_response": resp.text,
        "tokens_input": state.get("tokens_input", 0) + resp.tokens_input,
        "tokens_output": state.get("tokens_output", 0) + resp.tokens_output,
    }


def execute_action(state: AgentState) -> AgentState:
    from datachat.tools.pandas_executor import execute

    raw = state.get("llm_response", "").strip()
    description, action_expr = _parse_llm_response(raw)

    if not action_expr:
        # Treat the whole raw response as the expression (fallback)
        action_expr = raw
        description = "Computing a result"

    session_id = state["session_id"]
    df = _dataframe_store.get(session_id)

    if df is None:
        return {**state, "error": f"Session data not found — please re-upload the file"}

    result, is_error = execute(df, action_expr)
    history = list(state.get("action_history", []))
    history.append({
        "description": description or "Computing a result",
        "action": action_expr,
        "result": result,
        "is_error": is_error,
    })

    return {
        **state,
        "action_history": history,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def finalize(state: AgentState) -> AgentState:
    raw = state.get("llm_response", "")
    answer = raw[len("FINAL ANSWER:"):].strip() if raw.upper().startswith("FINAL ANSWER:") else raw
    _persist(state, answer, "completed")
    return {**state, "final_answer": answer}


def force_finalize(state: AgentState) -> AgentState:
    history = state.get("action_history", [])
    successful = [h for h in history if not h["is_error"]]
    if successful:
        lines = [f"- {h['description']}: {h['result'][:300]}" for h in successful]
        answer = "Based on the analysis completed so far:\n" + "\n".join(lines)
    else:
        answer = "I was unable to compute a result within the allowed steps. Try rephrasing your question."
    _persist(state, answer, "force_completed")
    return {**state, "final_answer": answer}


def handle_error(state: AgentState) -> AgentState:
    error = state.get("error", "Unknown error")
    _persist(state, f"Something went wrong: {error}", "failed")
    return {**state, "final_answer": f"Something went wrong: {error}"}


def release_session(session_id: str) -> None:
    """Free the in-memory DataFrame when a session is deleted."""
    _dataframe_store.pop(session_id, None)


def _persist(state: AgentState, answer: str, status: str) -> None:
    try:
        from datachat.db.session import create_db_session
        from datachat.db.models import RunRow, MessageRow

        with create_db_session() as db:
            run = db.get(RunRow, state["run_id"])
            if run:
                run.status = status
                run.tokens_input = state.get("tokens_input", 0)
                run.tokens_output = state.get("tokens_output", 0)

            trace = json.dumps(state.get("action_history", []))
            msg = MessageRow(
                session_id=state["session_id"],
                role="assistant",
                content=answer,
                reasoning_trace=trace,
            )
            db.add(msg)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Failed to persist agent result: %s", exc)
