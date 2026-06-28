"""Local execution sandbox — runs LLM-generated code over the FULL dataset.

Two execution modes:

* ``sql`` (preferred): the generated SQL runs in a DuckDB connection where the
  uploaded CSV is exposed as a view named ``data`` (via ``read_csv_auto`` so the
  100MB file is streamed, never fully loaded). The model writes ``SELECT ... FROM
  data ...``.
* ``pandas``: the generated code runs in a constrained namespace with a ``df``
  (the CSV loaded via pandas) and must assign its answer to ``result``.

Results are always BOUNDED to ``max_result_rows`` before leaving the engine — no
full data row ever flows back to the agent or the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass

import duckdb


class EngineError(Exception):
    """Raised when generated code fails to execute."""


@dataclass
class AnalysisResult:
    columns: list[str]
    rows: list[list]
    truncated: bool = False

    def as_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows, "truncated": self.truncated}


def _quote_path(csv_path: str) -> str:
    return csv_path.replace("'", "''")


def _strip_code_fence(code: str) -> str:
    text = (code or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop opening fence (``` or ```sql / ```python)
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # drop closing fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _jsonify(val):
    if val is None or isinstance(val, (str, int, float, bool)):
        return val
    return str(val)


class AnalysisEngine:
    """Runs generated SQL/pandas over one local CSV, returning bounded results."""

    def __init__(self, csv_path: str, max_result_rows: int = 1000) -> None:
        self.csv_path = csv_path
        self.max_result_rows = max(1, int(max_result_rows))

    def run(self, code: str, language: str = "sql") -> AnalysisResult:
        code = _strip_code_fence(code)
        if not code:
            raise EngineError("Empty code")
        if language == "pandas":
            return self._run_pandas(code)
        return self._run_sql(code)

    # --- SQL ---------------------------------------------------------------
    def _run_sql(self, sql: str) -> AnalysisResult:
        safe = _quote_path(self.csv_path)
        con = duckdb.connect(database=":memory:")
        try:
            con.execute(
                f"CREATE VIEW data AS SELECT * FROM read_csv_auto('{safe}')"
            )
            cur = con.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            fetched = cur.fetchmany(self.max_result_rows + 1)
            truncated = len(fetched) > self.max_result_rows
            rows = [
                [_jsonify(v) for v in rec]
                for rec in fetched[: self.max_result_rows]
            ]
            return AnalysisResult(columns=columns, rows=rows, truncated=truncated)
        except duckdb.Error as exc:
            raise EngineError(str(exc)) from exc
        finally:
            con.close()

    # --- pandas ------------------------------------------------------------
    def _run_pandas(self, code: str) -> AnalysisResult:
        import pandas as pd

        try:
            df = pd.read_csv(self.csv_path)
        except Exception as exc:  # noqa: BLE001 — surfaced as engine error
            raise EngineError(f"Failed to read CSV for pandas: {exc}") from exc

        namespace = {"df": df, "pd": pd, "result": None}
        try:
            exec(code, {"__builtins__": _SAFE_BUILTINS, "pd": pd}, namespace)  # noqa: S102
        except Exception as exc:  # noqa: BLE001 — surfaced as engine error
            raise EngineError(str(exc)) from exc

        result = namespace.get("result")
        return self._coerce_pandas_result(result, pd)

    def _coerce_pandas_result(self, result, pd) -> AnalysisResult:
        if result is None:
            raise EngineError("pandas code did not assign a `result`")
        if isinstance(result, pd.DataFrame):
            truncated = len(result) > self.max_result_rows
            bounded = result.head(self.max_result_rows)
            columns = [str(c) for c in bounded.columns]
            rows = [[_jsonify(v) for v in rec] for rec in bounded.itertuples(index=False, name=None)]
            return AnalysisResult(columns=columns, rows=rows, truncated=truncated)
        if isinstance(result, pd.Series):
            truncated = len(result) > self.max_result_rows
            bounded = result.head(self.max_result_rows)
            rows = [[_jsonify(idx), _jsonify(val)] for idx, val in bounded.items()]
            return AnalysisResult(columns=["index", "value"], rows=rows, truncated=truncated)
        # scalar
        return AnalysisResult(columns=["value"], rows=[[_jsonify(result)]], truncated=False)


_SAFE_BUILTINS = {
    "len": len,
    "range": range,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "round": round,
    "abs": abs,
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
}
