"""The PRIVACY GATE — the single choke point for every outbound LLM prompt.

Every agent node that calls the LLM builds its user prompt here. The gate:

- assembles the prompt from schema + computed aggregates ONLY;
- RAISES :class:`PrivacyViolation` if a raw-row object (a DataFrame, or a Series
  longer than the aggregate cap) is passed in, so a programming mistake can
  never leak raw data to the model.

``test_privacy_boundary`` asserts no raw cell value reaches any LLM request.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

# A result summary is an aggregate; anything longer than this is treated as a
# raw-row leak and rejected by the gate.
_AGGREGATE_ROW_CAP = 200


class PrivacyViolation(RuntimeError):
    """Raised when a raw-row / full-DataFrame object reaches the privacy gate."""


def _reject_raw(obj: Any, where: str) -> None:
    """Raise if ``obj`` is or contains a raw-row payload."""
    if isinstance(obj, pd.DataFrame):
        raise PrivacyViolation(
            f"raw DataFrame passed to the privacy gate ({where}); only schema + "
            f"aggregates may reach the LLM"
        )
    if isinstance(obj, pd.Series) and len(obj) > _AGGREGATE_ROW_CAP:
        raise PrivacyViolation(
            f"raw Series of length {len(obj)} passed to the privacy gate ({where})"
        )
    if isinstance(obj, np.ndarray) and obj.size > _AGGREGATE_ROW_CAP:
        raise PrivacyViolation(
            f"raw ndarray of size {obj.size} passed to the privacy gate ({where})"
        )
    if isinstance(obj, (list, tuple)) and len(obj) > _AGGREGATE_ROW_CAP:
        raise PrivacyViolation(
            f"oversized sequence (len {len(obj)}) passed to the privacy gate ({where})"
        )
    if isinstance(obj, dict):
        # A summary dict whose captured rows exceed the cap is a leak.
        rows = obj.get("rows")
        if isinstance(rows, (list, tuple)) and len(rows) > _AGGREGATE_ROW_CAP:
            raise PrivacyViolation(
                f"result summary with {len(rows)} rows exceeds aggregate cap ({where})"
            )


def build(
    *,
    profile: dict | None = None,
    plan: str | None = None,
    code: str | None = None,
    result_summary: Any = None,
    question: str | None = None,
    messages: list | None = None,
    extra: dict | None = None,
) -> str:
    """Assemble a privacy-safe user prompt from schema + aggregates only.

    Every value is checked by :func:`_reject_raw` before serialisation. Returns
    the prompt string the node sends to the LLM.
    """
    for name, value in (
        ("profile", profile),
        ("result_summary", result_summary),
        ("extra", extra),
    ):
        _reject_raw(value, name)

    sections: list[str] = []

    if question is not None:
        sections.append(f"## Question\n{question}")

    if messages:
        turns = []
        for turn in messages[-6:]:
            role = turn.get("role", "user")
            content = str(turn.get("content", ""))
            turns.append(f"- {role}: {content}")
        if turns:
            sections.append("## Conversation so far\n" + "\n".join(turns))

    if profile is not None:
        sections.append("## Dataset profile (schema + aggregates only)\n" + _dump(profile))

    if plan is not None:
        sections.append(f"## Plan\n{plan}")

    if code is not None:
        sections.append("## Code\n```python\n" + code + "\n```")

    if result_summary is not None:
        sections.append("## Execution result summary (aggregate)\n" + _dump(result_summary))

    if extra:
        sections.append("## Additional context\n" + _dump(extra))

    return "\n\n".join(sections)


def _dump(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, default=str)
    except (TypeError, ValueError):
        return str(value)
