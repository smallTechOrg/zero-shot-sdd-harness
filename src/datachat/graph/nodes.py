"""ReAct agent nodes."""
import json
import pathlib
from typing import Any

import pandas as pd

from datachat.graph.state import AgentState

# In-process DataFrame store keyed by session_id — released in every terminal node
_dataframe_store: dict[str, pd.DataFrame] = {}

_PROMPT_TEMPLATE = pathlib.Path(__file__).parent.parent / "prompts" / "plan_action.md"


def _load_prompt() -> str:
    return _PROMPT_TEMPLATE.read_text()


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
    from datachat.config.settings import get_settings

    history = state.get("action_history", [])
    history_text = (
        "\n".join(
            f"Action: {h['action']}\nResult: {h['result']}\n"
            for h in history
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

    action = state.get("llm_response", "").strip()
    session_id = state["session_id"]
    df = _dataframe_store.get(session_id)

    if df is None:
        return {**state, "error": f"DataFrame for session {session_id} disappeared during execution"}

    result, is_error = execute(df, action)
    history = list(state.get("action_history", []))
    history.append({"action": action, "result": result, "is_error": is_error})

    return {
        **state,
        "action_history": history,
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def finalize(state: AgentState) -> AgentState:
    raw = state.get("llm_response", "")
    answer = raw[len("FINAL ANSWER:"):].strip() if raw.upper().startswith("FINAL ANSWER:") else raw
    _release(state["session_id"])
    _persist(state, answer, "completed")
    return {**state, "final_answer": answer}


def force_finalize(state: AgentState) -> AgentState:
    history = state.get("action_history", [])
    successful = [h for h in history if not h["is_error"]]
    if successful:
        summary = "\n".join(f"- {h['action']} → {h['result'][:200]}" for h in successful)
        answer = f"Based on the computations completed (iteration limit reached):\n{summary}"
    else:
        answer = "The iteration limit was reached without producing useful results. Try a more specific question."
    _release(state["session_id"])
    _persist(state, answer, "force_completed")
    return {**state, "final_answer": answer}


def handle_error(state: AgentState) -> AgentState:
    error = state.get("error", "Unknown error")
    _release(state["session_id"])
    _persist(state, f"Agent error: {error}", "failed")
    return {**state, "final_answer": f"Agent error: {error}"}


def _release(session_id: str) -> None:
    _dataframe_store.pop(session_id, None)


def _persist(state: AgentState, answer: str, status: str) -> None:
    try:
        from datachat.db.session import create_db_session
        from datachat.db.models import RunRow, MessageRow, SessionRow
        import json

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
