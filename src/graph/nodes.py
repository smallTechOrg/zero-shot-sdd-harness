import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from graph.state import DataAnalysisState
from db.session import create_db_session
from db.models import UploadRow, AnalysisRow


# ---------------------------------------------------------------------------
# parse_upload
# ---------------------------------------------------------------------------

def parse_upload(state: DataAnalysisState) -> DataAnalysisState:
    """Load the uploaded file from disk into a pandas DataFrame."""
    try:
        upload_id = state["upload_id"]
        with create_db_session() as session:
            upload = session.get(UploadRow, upload_id)
            if upload is None:
                return {**state, "error": f"Upload '{upload_id}' not found in database."}
            filepath = upload.filepath

        path = Path(filepath)
        if not path.exists():
            return {**state, "error": f"File not found on disk: {filepath}"}

        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)

        return {**state, "dataframe": df, "filepath": filepath}
    except Exception as exc:
        return {**state, "error": str(exc)}


# ---------------------------------------------------------------------------
# run_preset_analysis
# ---------------------------------------------------------------------------

def run_preset_analysis(state: DataAnalysisState) -> DataAnalysisState:
    """Execute preset analyses. summary_stats is REAL; others are Phase 2 stubs."""
    analysis_type = state.get("analysis_type")
    df: pd.DataFrame | None = state.get("dataframe")

    if analysis_type == "summary_stats":
        return _summary_stats(state, df)
    else:
        # Phase 2 stub
        return {**state, "summary": "Coming in Phase 2", "chart_json": None, "table": None}


def _summary_stats(state: DataAnalysisState, df: pd.DataFrame | None) -> DataAnalysisState:
    """Compute real summary statistics for all numeric columns."""
    if df is None:
        return {**state, "error": "DataFrame not loaded."}

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if not numeric_cols:
        return {
            **state,
            "summary": "No numeric columns found in this dataset.",
            "chart_json": None,
            "table": [],
        }

    table_rows = []
    for col in numeric_cols:
        series = df[col].dropna()
        table_rows.append({
            "column": col,
            "count": int(series.count()),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "min": float(series.min()),
            "max": float(series.max()),
            "std": float(series.std()) if len(series) > 1 else 0.0,
        })

    n = len(numeric_cols)
    summary = f"Summary statistics for {n} numeric column{'s' if n != 1 else ''}: " + \
              ", ".join(numeric_cols)

    # Build Plotly bar chart using the first numeric column
    first_col = numeric_cols[0]
    series = df[first_col].dropna()
    fig = go.Figure(
        data=[go.Histogram(x=series.tolist(), name=first_col)],
        layout=go.Layout(
            title=f"Distribution of {first_col}",
            xaxis_title=first_col,
            yaxis_title="Count",
        ),
    )
    chart_json = pio.to_json(fig)

    return {**state, "summary": summary, "chart_json": chart_json, "table": table_rows}


# ---------------------------------------------------------------------------
# run_nl_query  (Phase 1 stub)
# ---------------------------------------------------------------------------

def run_nl_query(state: DataAnalysisState) -> DataAnalysisState:
    """Phase 1 stub — NL query requires Phase 3."""
    return {
        **state,
        "error": "NL query is not available until Phase 3. Please select a preset analysis type.",
    }


# ---------------------------------------------------------------------------
# format_response
# ---------------------------------------------------------------------------

def format_response(state: DataAnalysisState) -> DataAnalysisState:
    """Normalise the output fields before writing to DB."""
    summary = state.get("summary") or "Analysis complete."

    # Validate chart_json — must be a string or None
    chart_json = state.get("chart_json")
    if chart_json is not None and not isinstance(chart_json, str):
        chart_json = None

    # Truncate table to 1000 rows
    table = state.get("table")
    if isinstance(table, list) and len(table) > 1000:
        table = table[:1000]

    return {**state, "summary": summary, "chart_json": chart_json, "table": table}


# ---------------------------------------------------------------------------
# handle_error
# ---------------------------------------------------------------------------

def handle_error(state: DataAnalysisState) -> DataAnalysisState:
    return {**state, "status": "failed"}


# ---------------------------------------------------------------------------
# finalize
# ---------------------------------------------------------------------------

def finalize(state: DataAnalysisState) -> DataAnalysisState:
    """Write results back to the analyses table and mark completed."""
    status = state.get("status") or "completed"
    analysis_id = state.get("run_id")
    table = state.get("table")

    try:
        with create_db_session() as session:
            row = session.get(AnalysisRow, analysis_id)
            if row is not None:
                row.status = status
                row.summary = state.get("summary")
                row.chart_json = state.get("chart_json")
                row.table_json = json.dumps(table) if table is not None else None
                row.error_message = state.get("error")
    except Exception as exc:
        # Log but do not crash the graph
        import structlog
        structlog.get_logger().error("finalize_db_write_failed", error=str(exc))

    return {**state, "status": status}
