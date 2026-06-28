"""Local code-execution sandbox.

Runs LLM-generated pandas code in a child Python subprocess over the FULL CSV
file. The child namespace contains only `pd`, `np` and the DataFrame(s); the
generated code assigns `result` and optionally `chart` (a dict descriptor) and
`table` (a DataFrame). The child serializes those to JSON on stdout; the parent
reads them back, builds a Plotly chart_spec from the `chart` descriptor, and
coerces `table` to JSON records.

The LLM is NEVER called from here — this is the only place the full data lives,
and it stays local.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT = 60

# The child runner script. It is fully self-contained (no project imports) so it
# can run as a bare `python -c` subprocess with only pandas/numpy available.
_CHILD_RUNNER = r'''
import json, sys, traceback

def _emit(payload):
    sys.stdout.write("\n@@SANDBOX_RESULT@@" + json.dumps(payload) + "@@END@@\n")

def _jsonable(obj):
    import numpy as np
    import pandas as pd
    if obj is None:
        return None
    if isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, pd.Series):
        return {str(_jsonable(k)): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, pd.DataFrame):
        return _df_records(obj)
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    try:
        return _jsonable(obj.item())
    except Exception:
        return str(obj)

def _df_records(df):
    import pandas as pd
    df2 = df.reset_index() if df.index.name is not None or not isinstance(df.index, pd.RangeIndex) else df
    safe = df2.astype(object).where(pd.notnull(df2), None)
    out = []
    for rec in safe.to_dict(orient="records"):
        out.append({str(k): _jsonable(v) for k, v in rec.items()})
    return out

def main():
    import pandas as pd
    import numpy as np
    args = json.loads(sys.argv[1])
    csv_paths = args["csv_paths"]
    code = args["code"]

    namespace = {"pd": pd, "np": np}
    # Load the FULL file(s). Phase 1: a single frame bound to "df".
    for name, path in csv_paths.items():
        namespace[name] = pd.read_csv(path)

    try:
        exec(compile(code, "<generated>", "exec"), namespace)
    except Exception:
        _emit({"ok": False, "error": traceback.format_exc()})
        return

    if "result" not in namespace:
        _emit({"ok": False,
               "error": "Generated code did not assign a `result` variable."})
        return

    result = _jsonable(namespace.get("result"))
    chart = namespace.get("chart")
    table = namespace.get("table")
    _emit({
        "ok": True,
        "result": result,
        "chart": _jsonable(chart) if chart is not None else None,
        "table": _df_records(table) if isinstance(table, pd.DataFrame)
                 else (_jsonable(table) if table is not None else None),
    })

main()
'''

_MARK_START = "@@SANDBOX_RESULT@@"
_MARK_END = "@@END@@"


@dataclass
class SandboxResult:
    ok: bool
    result: object = None
    chart: dict | None = None          # raw chart descriptor from the code
    chart_spec: dict | None = None     # built Plotly JSON spec
    table: list[dict] | None = None
    stdout: str = ""
    error: str | None = None
    duration_ms: int = 0


def _build_chart_spec(chart: dict | None) -> dict | None:
    """Turn the code's `chart` descriptor into a minimal Plotly JSON spec.

    Descriptor shape: {"type": "bar"|"line"|"scatter"|"pie", "x": [...],
    "y": [...], "title": "...", "x_label": "...", "y_label": "..."}.
    Returns None if there's nothing chartable.
    """
    if not isinstance(chart, dict):
        return None
    ctype = str(chart.get("type", "bar")).lower()
    x = chart.get("x")
    y = chart.get("y")
    if x is None and y is None:
        return None

    if ctype == "pie":
        trace = {"type": "pie", "labels": x, "values": y}
    elif ctype in ("line", "scatter"):
        trace = {
            "type": "scatter",
            "mode": "lines" if ctype == "line" else "markers",
            "x": x,
            "y": y,
        }
    else:  # default bar
        trace = {"type": "bar", "x": x, "y": y}

    layout: dict = {}
    if chart.get("title"):
        layout["title"] = {"text": str(chart["title"])}
    if chart.get("x_label"):
        layout["xaxis"] = {"title": {"text": str(chart["x_label"])}}
    if chart.get("y_label"):
        layout["yaxis"] = {"title": {"text": str(chart["y_label"])}}

    return {"data": [trace], "layout": layout}


def run_code(
    csv_paths: dict[str, str], code: str, *, timeout: int = DEFAULT_TIMEOUT
) -> SandboxResult:
    """Execute `code` in a child subprocess over the full CSV file(s)."""
    import time

    # Validate paths up front so a bad path is a clean error, not a child crash.
    for name, path in csv_paths.items():
        if not Path(path).exists():
            return SandboxResult(
                ok=False, error=f"CSV path for `{name}` does not exist: {path}"
            )

    payload = json.dumps({"csv_paths": csv_paths, "code": code})
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _CHILD_RUNNER, payload],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        elapsed = int((time.monotonic() - started) * 1000)
        return SandboxResult(
            ok=False,
            error=f"Code execution timed out after {timeout}s.",
            duration_ms=elapsed,
        )
    except Exception as exc:  # spawning failed
        elapsed = int((time.monotonic() - started) * 1000)
        return SandboxResult(ok=False, error=f"Sandbox failed to start: {exc}",
                             duration_ms=elapsed)

    elapsed = int((time.monotonic() - started) * 1000)
    raw = proc.stdout or ""

    start = raw.find(_MARK_START)
    end = raw.find(_MARK_END, start) if start != -1 else -1
    if start == -1 or end == -1:
        # No structured payload — surface stderr / exit code as the error.
        err = (proc.stderr or "").strip() or f"Process exited {proc.returncode} with no result."
        return SandboxResult(ok=False, error=err, stdout=raw, duration_ms=elapsed)

    body = raw[start + len(_MARK_START):end]
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        return SandboxResult(
            ok=False, error=f"Could not decode sandbox output: {exc}",
            stdout=raw, duration_ms=elapsed,
        )

    if not parsed.get("ok"):
        return SandboxResult(
            ok=False, error=parsed.get("error", "Unknown sandbox error"),
            stdout=raw, duration_ms=elapsed,
        )

    chart = parsed.get("chart")
    return SandboxResult(
        ok=True,
        result=parsed.get("result"),
        chart=chart if isinstance(chart, dict) else None,
        chart_spec=_build_chart_spec(chart),
        table=parsed.get("table"),
        stdout=raw,
        duration_ms=elapsed,
    )
