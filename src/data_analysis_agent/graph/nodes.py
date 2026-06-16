import sqlite3

import pandas as pd
import structlog

from data_analysis_agent.graph.state import AgentState

log = structlog.get_logger()

_db_cache: dict[str, sqlite3.Connection] = {}


def _cleanup_db(run_id: str) -> None:
    conn = _db_cache.pop(run_id, None)
    if conn:
        try:
            conn.close()
        except Exception:
            pass


def _strip_sql_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()
    return text


def _build_plan_prompt(state: AgentState) -> str:
    columns = ", ".join(state.get("column_names", []))
    question = state["question"]
    history: list[dict] = state.get("query_history", [])

    lines = [
        "<node:plan_query>",
        "You are a data analyst with access to a SQL query executor.",
        "",
        "Table: data",
        f"Columns: {columns}",
        "",
        f"User question: {question}",
    ]

    if history:
        lines.append("")
        lines.append("Previous queries and results:")
        for i, entry in enumerate(history, 1):
            lines.append(f"[{i}] SQL: {entry['sql']}")
            lines.append(f"    Result:\n{entry['result']}")

    lines.extend([
        "",
        "Decide your next step:",
        "- If you need more data: respond with a single SQL SELECT query and nothing else.",
        "- If you have enough information: respond with exactly:",
        "  FINAL ANSWER: <your complete answer here>",
        "",
        "Do not include markdown, backticks, or explanations when writing SQL.",
    ])

    return "\n".join(lines)


def load_data(state: AgentState) -> AgentState:
    try:
        df = pd.read_csv(state["csv_path"])
        column_names = list(df.columns)
        row_count = len(df)

        conn = sqlite3.connect(":memory:")
        df.to_sql("data", conn, index=False, if_exists="replace")
        _db_cache[state["run_id"]] = conn

        log.info("load_data.done", run_id=state.get("run_id"), rows=row_count, cols=len(column_names))
        return {
            **state,
            "column_names": column_names,
            "row_count": row_count,
            "query_history": [],
            "iteration_count": 0,
        }
    except Exception as exc:
        log.error("load_data.failed", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"Failed to read CSV: {exc}"}


def plan_query(state: AgentState) -> AgentState:
    try:
        from data_analysis_agent.llm.client import get_llm_client

        prompt = _build_plan_prompt(state)
        result = get_llm_client().complete(prompt)
        response = result.text.strip()

        prior_cost = state.get("estimated_cost_usd") or 0.0
        new_state = {
            **state,
            "llm_response": response,
            "input_tokens": state.get("input_tokens", 0) + result.input_tokens,
            "output_tokens": state.get("output_tokens", 0) + result.output_tokens,
            "total_tokens": state.get("total_tokens", 0) + result.total_tokens,
            "estimated_cost_usd": prior_cost + (result.estimated_cost_usd or 0.0),
            "api_request_count": state.get("api_request_count", 0) + 1,
        }

        if response.upper().startswith("FINAL ANSWER:"):
            new_state["answer"] = response[len("FINAL ANSWER:"):].strip()
            log.info("plan_query.final_answer", run_id=state.get("run_id"), iterations=state.get("iteration_count", 0))
        else:
            log.info("plan_query.sql_requested", run_id=state.get("run_id"), iteration=state.get("iteration_count", 0))

        return new_state
    except Exception as exc:
        log.error("plan_query.failed", run_id=state.get("run_id"), error=str(exc))
        _cleanup_db(state.get("run_id", ""))
        return {**state, "error": f"LLM query planning failed: {exc}"}


def execute_query(state: AgentState) -> AgentState:
    try:
        from data_analysis_agent.config.settings import get_settings
        max_iterations = get_settings().max_agent_iterations

        run_id = state["run_id"]
        sql = _strip_sql_fences(state.get("llm_response", ""))

        if not sql.upper().lstrip().startswith("SELECT"):
            _cleanup_db(run_id)
            return {**state, "error": f"LLM returned non-SELECT SQL: {sql[:120]}"}

        conn = _db_cache.get(run_id)
        if conn is None:
            return {**state, "error": "In-memory DB not found — load_data must precede execute_query"}

        cursor = conn.execute(sql)
        rows = cursor.fetchmany(200)
        col_headers = [d[0] for d in cursor.description] if cursor.description else []

        result_lines = [",".join(col_headers)]
        for row in rows:
            result_lines.append(",".join("" if v is None else str(v) for v in row))
        result_str = "\n".join(result_lines)

        history = list(state.get("query_history", []))
        history.append({"sql": sql, "result": result_str})
        iteration_count = state.get("iteration_count", 0) + 1

        log.info("execute_query.done", run_id=run_id, iteration=iteration_count, result_rows=len(rows))

        new_state = {**state, "query_history": history, "iteration_count": iteration_count}

        if iteration_count >= max_iterations:
            _cleanup_db(run_id)
            return {**new_state, "error": f"Max iterations ({max_iterations}) reached without a final answer"}

        return new_state
    except Exception as exc:
        log.error("execute_query.failed", run_id=state.get("run_id"), error=str(exc))
        _cleanup_db(state.get("run_id", ""))
        return {**state, "error": f"SQL execution failed: {exc}"}


def finalize(state: AgentState) -> AgentState:
    try:
        from data_analysis_agent.db.session import create_db_session
        from data_analysis_agent.db.models import QueryRecordRow, AgentRunRow
        with create_db_session() as session:
            qr = session.get(QueryRecordRow, state["query_record_id"])
            if qr:
                qr.answer = state.get("answer", "")
                qr.status = "completed"
                qr.input_tokens = state.get("input_tokens", 0)
                qr.output_tokens = state.get("output_tokens", 0)
                qr.total_tokens = state.get("total_tokens", 0)
                qr.estimated_cost_usd = state.get("estimated_cost_usd")
                qr.api_request_count = state.get("api_request_count", 1)
                qr.iteration_count = state.get("iteration_count", 0)
            run = session.get(AgentRunRow, state["run_id"])
            if run:
                run.status = "completed"
        _cleanup_db(state["run_id"])
        log.info("finalize.done", run_id=state.get("run_id"))
        return state
    except Exception as exc:
        log.error("finalize.failed", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"Finalize failed: {exc}"}


def handle_error(state: AgentState) -> AgentState:
    try:
        from data_analysis_agent.db.session import create_db_session
        from data_analysis_agent.db.models import QueryRecordRow, AgentRunRow
        error_msg = state.get("error", "Unknown error")
        with create_db_session() as session:
            qr = session.get(QueryRecordRow, state.get("query_record_id", ""))
            if qr:
                qr.status = "failed"
                qr.error_message = error_msg
            run = session.get(AgentRunRow, state.get("run_id", ""))
            if run:
                run.status = "failed"
                run.error_message = error_msg
        log.error("pipeline.failed", run_id=state.get("run_id"), error=error_msg)
    except Exception as exc:
        log.error("handle_error.db_write_failed", error=str(exc))
    finally:
        _cleanup_db(state.get("run_id", ""))
    return state
