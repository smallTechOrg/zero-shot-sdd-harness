import json
import logging
from pathlib import Path

import structlog

from graph.state import AgentState
from llm.client import LLMClient

logger = structlog.get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def _extract_json(text: str) -> str:
    """Strip markdown code fences if present and return raw JSON string."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # remove first line (```json or ```) and last line (```)
        inner = lines[1:-1]
        text = "\n".join(inner).strip()
    return text


# ---------------------------------------------------------------------------
# ingest_csv
# ---------------------------------------------------------------------------

def ingest_csv(state: AgentState) -> AgentState:
    try:
        import pandas as pd

        dataset_path = state["dataset_path"]
        dataset_id = state.get("dataset_id")

        df = pd.read_csv(dataset_path)

        # Cap at 20 columns
        cols = list(df.columns[:20])
        df_display = df[cols]

        rows, total_cols = df.shape

        lines = [
            f"Shape: {rows} rows x {total_cols} columns",
            "",
            "Columns and dtypes:",
        ]
        for col in cols:
            lines.append(f"  {col}: {df[col].dtype}")

        if total_cols > 20:
            lines.append(f"  ... ({total_cols - 20} more columns not shown)")

        lines.append("")
        lines.append("Sample (first 5 rows):")
        sample = df_display.head(5)
        # Build a simple text table without requiring tabulate
        header = " | ".join(str(c) for c in sample.columns)
        sep = " | ".join("-" * max(len(str(c)), 4) for c in sample.columns)
        lines.append(header)
        lines.append(sep)
        for _, row_vals in sample.iterrows():
            lines.append(" | ".join(str(v) for v in row_vals))

        schema_summary = "\n".join(lines)

        # Update DatasetRow metadata if dataset_id is known
        if dataset_id:
            try:
                from db.session import create_db_session
                from db.models import DatasetRow

                with create_db_session() as session:
                    row = session.get(DatasetRow, dataset_id)
                    if row is not None:
                        row.row_count = rows
                        row.column_names_json = json.dumps(list(df.columns))
            except Exception as db_exc:
                logger.warning("ingest_csv: db update failed", error=str(db_exc))

        return {**state, "schema_summary": schema_summary}

    except Exception as exc:
        logger.error("ingest_csv: failed", error=str(exc))
        return {**state, "error": f"ingest_csv: {exc}"}


# ---------------------------------------------------------------------------
# plan_analysis
# ---------------------------------------------------------------------------

def plan_analysis(state: AgentState) -> AgentState:
    try:
        schema_summary = state.get("schema_summary", "")
        question = state.get("question", "")
        system_prompt = _load_prompt("analysis_plan.md")

        user_message = (
            f"CSV Schema:\n{schema_summary}\n\nQuestion: {question}"
        )

        client = LLMClient()

        def _try_parse(raw: str) -> dict | None:
            try:
                return json.loads(_extract_json(raw))
            except (json.JSONDecodeError, ValueError):
                return None

        raw = client.call_model(user_message, system=system_prompt)
        plan = _try_parse(raw)

        if plan is None:
            # Retry once
            raw2 = client.call_model(user_message, system=system_prompt)
            plan = _try_parse(raw2)
            if plan is None:
                err = f"plan_analysis: invalid JSON after retry: {raw2[:200]}"
                logger.error("plan_analysis: failed after retry", raw=raw2[:200])
                return {**state, "error": err}

        if "pandas_ops" not in plan or not isinstance(plan["pandas_ops"], list):
            err = "plan_analysis: response missing 'pandas_ops' list"
            logger.error("plan_analysis: bad plan structure", plan=str(plan)[:200])
            return {**state, "error": err}

        return {**state, "analysis_plan": plan}

    except Exception as exc:
        logger.error("plan_analysis: exception", error=str(exc))
        return {**state, "error": f"plan_analysis: {exc}"}


# ---------------------------------------------------------------------------
# execute_analysis
# ---------------------------------------------------------------------------

def execute_analysis(state: AgentState) -> AgentState:
    try:
        import pandas as pd

        dataset_path = state["dataset_path"]
        analysis_plan = state.get("analysis_plan", {})
        ops = analysis_plan.get("pandas_ops", [])

        df = pd.read_csv(dataset_path)
        result = df  # running result

        for op_spec in ops:
            op_name = op_spec.get("op")

            if op_name == "groupby":
                by = op_spec["by"]
                agg = op_spec.get("agg", {})
                result = df.groupby(by).agg(agg).reset_index()

            elif op_name == "agg":
                agg_dict = op_spec.get("agg", {})
                result = df.agg(agg_dict)

            elif op_name == "sort_values":
                by = op_spec["by"]
                ascending = op_spec.get("ascending", True)
                result = result.sort_values(by=by, ascending=ascending)

            elif op_name == "head":
                n = op_spec.get("n", 10)
                result = result.head(n)

            elif op_name == "describe":
                result = df.describe()

            elif op_name == "value_counts":
                col = op_spec["column"]
                result = df[col].value_counts().reset_index()
                result.columns = [col, "count"]

            else:
                logger.warning("execute_analysis: unknown op, skipping", op=op_name)

        # Serialize result
        if hasattr(result, "to_dict"):
            if hasattr(result, "columns"):
                computed_data = {"result": result.to_dict(orient="records")}
            else:
                computed_data = {"result": result.to_dict()}
        else:
            computed_data = {"result": str(result)}

        return {**state, "computed_data": computed_data}

    except Exception as exc:
        logger.error("execute_analysis: exception", error=str(exc))
        return {**state, "error": f"execute_analysis: {exc}"}


# ---------------------------------------------------------------------------
# generate_answer
# ---------------------------------------------------------------------------

def generate_answer(state: AgentState) -> AgentState:
    try:
        question = state.get("question", "")
        computed_data = state.get("computed_data", {})
        schema_summary = state.get("schema_summary", "")
        system_prompt = _load_prompt("answer.md")

        computed_data_str = json.dumps(computed_data)[:4000]
        user_msg = (
            f"Question: {question}\n\n"
            f"Schema:\n{schema_summary}\n\n"
            f"Computed data:\n{computed_data_str}"
        )

        client = LLMClient()
        answer_text = client.call_model(user_msg, system=system_prompt)

        return {**state, "answer_text": answer_text}

    except Exception as exc:
        logger.error("generate_answer: exception", error=str(exc))
        return {**state, "error": f"generate_answer: {exc}"}


# ---------------------------------------------------------------------------
# generate_chart
# ---------------------------------------------------------------------------

def generate_chart(state: AgentState) -> AgentState:
    try:
        import plotly.graph_objects as go
        import plotly.io as pio

        computed_data = state.get("computed_data", {})
        analysis_plan = state.get("analysis_plan", {})
        question = state.get("question", "")

        chart_type = analysis_plan.get("chart_type", "bar")
        chart_cols = analysis_plan.get("chart_columns", {})
        result = computed_data.get("result")

        if not isinstance(result, list) or len(result) == 0:
            return {**state, "chart_json": None}

        x_col = chart_cols.get("x")
        y_col = chart_cols.get("y")
        x_vals = [row.get(x_col) for row in result] if x_col else list(range(len(result)))
        y_vals = [row.get(y_col) for row in result] if y_col else [list(row.values())[-1] for row in result]

        if chart_type == "bar":
            trace = go.Bar(x=x_vals, y=y_vals)
        elif chart_type == "line":
            trace = go.Scatter(x=x_vals, y=y_vals, mode="lines+markers")
        elif chart_type == "scatter":
            trace = go.Scatter(x=x_vals, y=y_vals, mode="markers")
        elif chart_type == "pie":
            trace = go.Pie(labels=x_vals, values=y_vals)
        elif chart_type == "histogram":
            trace = go.Histogram(x=x_vals)
        else:
            logger.warning("generate_chart: unrecognized chart_type", chart_type=chart_type)
            return {**state, "chart_json": None}

        fig = go.Figure(
            data=[trace],
            layout=go.Layout(
                title=question[:80] if question else "Analysis Result",
                xaxis_title=x_col or "",
                yaxis_title=y_col or "",
            ),
        )
        chart_json = pio.to_json(fig)

        # Validate it's parseable
        json.loads(chart_json)

        return {**state, "chart_json": chart_json}

    except Exception as exc:
        logger.warning("generate_chart: exception (non-fatal)", error=str(exc))
        return {**state, "chart_json": None}


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

def finalize(state: AgentState) -> AgentState:
    analysis_id = state.get("analysis_id")
    try:
        if analysis_id:
            from db.session import create_db_session
            from db.models import AnalysisRow

            with create_db_session() as session:
                row = session.get(AnalysisRow, analysis_id)
                if row is not None:
                    row.status = "completed"
                    row.answer_text = state.get("answer_text")
                    row.chart_json = state.get("chart_json")
                    row.error_message = None
    except Exception as exc:
        logger.error("finalize: db write failed (non-fatal)", error=str(exc), analysis_id=analysis_id)

    return {**state, "status": "completed"}


# ---------------------------------------------------------------------------
# handle_error
# ---------------------------------------------------------------------------

def handle_error(state: AgentState) -> AgentState:
    analysis_id = state.get("analysis_id")
    error = state.get("error")

    logger.error(
        "analysis.failed",
        run_id=state.get("run_id"),
        analysis_id=analysis_id,
        dataset_id=state.get("dataset_id"),
        error=error,
    )

    try:
        if analysis_id:
            from db.session import create_db_session
            from db.models import AnalysisRow

            with create_db_session() as session:
                row = session.get(AnalysisRow, analysis_id)
                if row is not None:
                    row.status = "failed"
                    row.error_message = error
    except Exception as exc:
        logger.error("handle_error: db write failed", error=str(exc), analysis_id=analysis_id)

    return {**state, "status": "failed"}
