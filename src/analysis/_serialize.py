"""JSON-safety helpers shared across the analysis modules.

Everything these modules return is stored as JSON and/or sent to the LLM, so
numpy scalars, pandas timestamps, and NaN/NaT must be coerced to plain Python
values (with NaN -> None) before they leave this package.
"""
from __future__ import annotations

import math
from typing import Any


def to_json_safe(value: Any) -> Any:
    """Recursively coerce a value into something ``json.dumps`` accepts.

    - numpy scalars -> python scalars (via ``.item()``)
    - NaN / NaT / infinities -> None
    - pandas/py datetimes -> ISO strings
    - dict / list / tuple / set -> recursively coerced
    - anything else unrecognised -> ``str(value)``
    """
    # Fast path for the common JSON primitives.
    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    # numpy / pandas scalar with an ``.item()`` accessor.
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return to_json_safe(item())
        except (ValueError, TypeError):
            pass

    # Containers.
    if isinstance(value, dict):
        return {str(to_json_safe(k)): to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(v) for v in value]

    # bytes.
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8", "replace")
        except Exception:  # pragma: no cover - defensive
            return str(value)

    # Datetime-like: prefer ISO format when available.
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:  # pragma: no cover - defensive
            pass

    # pandas NaT / numpy nan that slipped through as objects.
    try:
        if value != value:  # NaN is the only value not equal to itself.
            return None
    except Exception:  # pragma: no cover - defensive
        pass

    return str(value)
