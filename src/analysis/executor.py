"""Run LLM-generated pandas code against the full dataset in a timed subprocess.

Pattern #22 (LLM-Generated Code Execution). The generated ``code`` runs inside a
*separate* Python process with a wall-clock timeout so runaway code cannot hang
the request. The raw data never leaves that subprocess — only the aggregated
``result`` dict (JSON) is returned to the parent.

``run_pandas`` NEVER raises: every failure (traceback, timeout, missing result,
non-serializable result) is returned as an error string so the caller can drive
the bounded retry loop.
"""
from __future__ import annotations

import json
import subprocess
import sys

from analysis._serialize import to_json_safe

# Rows above this in ``result["table"]`` are truncated so charts/tables stay small.
MAX_TABLE_ROWS = 2000

# Source executed via ``python -c`` in the child process. It is fully
# self-contained (only stdlib + pandas) so it does not depend on ``src`` being
# on the child's ``sys.path``. Inputs arrive as JSON on stdin; the aggregated
# result is emitted as JSON on stdout.
_RUNNER_SRC = r'''
import json, sys, math, traceback

def _json_safe(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_safe(item())
        except (ValueError, TypeError):
            pass
    if isinstance(value, dict):
        return {str(_json_safe(k)): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return str(value)
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        try:
            return iso()
        except Exception:
            pass
    try:
        if value != value:
            return None
    except Exception:
        pass
    return str(value)

MAX_TABLE_ROWS = %(max_rows)d

def main():
    payload = json.loads(sys.stdin.read())
    code = payload["code"]
    data_path = payload["data_path"]
    file_format = (payload.get("file_format") or "").lower()

    import pandas as pd
    if file_format == "csv":
        df = pd.read_csv(data_path)
    elif file_format in ("xlsx", "xls"):
        df = pd.read_excel(data_path, engine="openpyxl")
    else:
        raise ValueError("Unsupported file_format: %%r" %% (file_format,))

    ns = {"pd": pd, "df": df}
    exec(compile(code, "<generated_code>", "exec"), ns)

    if "result" not in ns:
        raise RuntimeError(
            "Generated code did not assign a `result` variable."
        )
    result = ns["result"]
    if not isinstance(result, dict):
        raise RuntimeError(
            "`result` must be a dict, got %%s." %% (type(result).__name__,)
        )

    result = _json_safe(result)

    table = result.get("table")
    if isinstance(table, list) and len(table) > MAX_TABLE_ROWS:
        result["table"] = table[: MAX_TABLE_ROWS]
        result["table_truncated"] = True
        result["table_truncation_note"] = (
            "table truncated to %%d of %%d rows" %% (MAX_TABLE_ROWS, len(table))
        )

    sys.stdout.write(json.dumps(result))

try:
    main()
except Exception:
    traceback.print_exc()
    sys.exit(1)
''' % {"max_rows": MAX_TABLE_ROWS}


def _error_tail(text: str, limit: int = 2000) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return "..." + text[-limit:]
    return text


def run_pandas(
    code: str,
    data_path: str,
    file_format: str,
    timeout: int,
) -> tuple[dict | None, str | None]:
    """Execute ``code`` against the full dataset in a timed subprocess.

    Returns ``(result, None)`` on success — ``result`` is the aggregated,
    JSON-safe ``{"value", "table", "columns", ...}`` dict the code assigned.
    Returns ``(None, error)`` on any failure (non-zero exit, traceback, timeout,
    missing/invalid/non-serializable result). Never raises.
    """
    payload = json.dumps(
        {"code": code, "data_path": data_path, "file_format": file_format}
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", _RUNNER_SRC],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, (
            f"Execution timed out after {timeout}s "
            f"(the generated code did not finish in time)."
        )
    except Exception as exc:  # noqa: BLE001 - never raise to the caller
        return None, f"Failed to launch execution subprocess: {exc}"

    if proc.returncode != 0:
        detail = _error_tail(proc.stderr) or _error_tail(proc.stdout) or (
            f"subprocess exited with code {proc.returncode}"
        )
        return None, detail

    stdout = (proc.stdout or "").strip()
    if not stdout:
        return None, (
            "Execution produced no output; the code did not emit a `result`."
        )

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, (
            f"Could not decode execution result as JSON: {exc}. "
            f"Output tail: {_error_tail(stdout, 400)}"
        )

    if not isinstance(result, dict):
        return None, "Execution `result` was not a JSON object."

    # Defensive: the subprocess already coerces, but guarantee JSON-safety here.
    return to_json_safe(result), None
