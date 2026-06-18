import json
from typing import Any

import pandas as pd

from datachat.graph.agent import agent_graph
from datachat.graph.nodes import _dataframe_store
from datachat.graph.state import AgentState
from datachat.db.session import create_db_session
from datachat.db.models import RunRow


def run_agent(session_id: str, question: str, df: pd.DataFrame) -> dict[str, Any]:
    """
    Run the ReAct agent for a question against the given DataFrame.
    Returns {"answer": str, "reasoning_trace": list, "llm_provider": str, "run_id": str}.
    """
    _dataframe_store[session_id] = df

    with create_db_session() as db:
        run = RunRow(session_id=session_id)
        db.add(run)
        db.flush()
        run_id = run.id

    initial: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "question": question,
    }

    final = agent_graph.invoke(initial)

    from datachat.llm.client import get_llm_client
    from datachat.config.settings import get_settings
    llm_provider = get_settings().resolved_llm_provider

    return {
        "answer": final.get("final_answer", ""),
        "reasoning_trace": final.get("action_history", []),
        "llm_provider": llm_provider,
        "run_id": run_id,
    }
