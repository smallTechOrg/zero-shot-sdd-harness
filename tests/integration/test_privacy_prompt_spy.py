"""Headline privacy guarantee (analyze_dataset.md:43): the LLM only ever sees
schema + sample rows + question — NEVER a full data row.

We engineer a unique sentinel value into a raw row that lives *beyond* the
sampled window (and is not a schema field or a sampled value), run the real
code-generation + answer-composition path through the graph, and intercept
every prompt at the ``LLMClient`` boundary. The sentinel must appear in NONE of
the captured LLM payloads — proving the full dataset never leaves the box.

Spying at the client boundary means this needs no live Gemini call: the spy
captures the prompt and returns canned (valid) responses so the graph proceeds
and real pandas still executes over the FULL file locally (where the sentinel
DOES live — that is the point).
"""
from __future__ import annotations

import io

from db.models import DatasetRow
from db.session import create_db_session
from graph.runner import run_analysis
from llm.client import LLMClient

# A value that appears in exactly ONE full data row, well past the 5-row sample
# window, and never as a column name or a sampled value.
_SENTINEL = "ZZ_PRIVACY_SENTINEL_9f3a7c__DO_NOT_LEAK"

# 12 rows. Sample window = first 5 (profiler default sample_n=5). The sentinel
# sits in the 'note' column of row index 8 — outside the sample. The aggregation
# the canned code performs is region -> amount, so the sentinel column never
# reaches the write_answer result payload either.
_ROWS = [
    ("North", 100, "alpha"),
    ("South", 200, "beta"),
    ("North", 150, "gamma"),
    ("West", 50, "delta"),
    ("South", 300, "epsilon"),
    ("East", 10, "zeta"),
    ("North", 20, "eta"),
    ("West", 70, "theta"),
    ("South", 40, _SENTINEL),  # index 8 — beyond the sample window
    ("East", 90, "iota"),
    ("North", 60, "kappa"),
    ("West", 30, "lambda"),
]


def _csv_bytes() -> bytes:
    lines = ["region,amount,note"]
    lines += [f"{r},{a},{n}" for (r, a, n) in _ROWS]
    return ("\n".join(lines) + "\n").encode()


_CANNED_CODE = """```python
result = {
    "value": None,
    "table": df.groupby("region")["amount"].sum().reset_index().to_dict("records"),
    "columns": ["region", "amount"],
}
```"""

_CANNED_ANSWER = (
    '{"answer": "Totals by region computed.", '
    '"narrative": "Region totals over the full dataset.", '
    '"key_numbers": [{"label": "Regions", "value": "4"}], '
    '"chart": {"mark": "bar", "x": "region", "y": "amount", "title": "By region"}}'
)


def test_full_rows_never_reach_the_llm(api_client, monkeypatch):
    # Upload + profile via the real endpoint (stores the FULL file on disk).
    resp = api_client.post(
        "/datasets",
        files={"file": ("priv.csv", io.BytesIO(_csv_bytes()), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    dataset_id = resp.json()["data"]["id"]

    # Sanity: the sentinel really is in the stored raw file (else the test proves
    # nothing). Also confirm it is NOT in the persisted profile (schema/sample).
    with create_db_session() as session:
        ds = session.get(DatasetRow, dataset_id)
        file_path = ds.file_path
        profile_json = ds.profile_json
    with open(file_path, "r", encoding="utf-8") as fh:
        raw_file = fh.read()
    assert _SENTINEL in raw_file, "fixture broken: sentinel not in the raw file"
    assert _SENTINEL not in profile_json, (
        "sentinel leaked into the stored profile (schema/sample) — fixture is "
        "not exercising the beyond-sample guarantee"
    )

    # Intercept EVERY prompt at the client boundary; return canned valid output.
    captured: list[str] = []

    def _spy_call_model(self, prompt, *, system=None):
        captured.append(prompt)
        if system is not None:
            captured.append(system)
        # write_answer prompt asks for a "single JSON object"; generate_code asks
        # for a fenced python block assigning `result`.
        if "JSON object" in prompt:
            return _CANNED_ANSWER
        return _CANNED_CODE

    monkeypatch.setattr(LLMClient, "__init__", lambda self: None)
    monkeypatch.setattr(LLMClient, "call_model", _spy_call_model)

    run_id = run_analysis(dataset_id, "What is the total amount by region?")

    # The run must actually have called the LLM (both nodes), else we would be
    # trivially asserting on an empty capture.
    assert captured, "no LLM prompts were captured — the path did not run"
    assert any("JSON object" in p for p in captured), "write_answer never ran"
    assert any("result" in p for p in captured), "generate_code never ran"

    # THE GUARANTEE: the sentinel raw-row value appears in NO captured payload.
    for i, payload in enumerate(captured):
        assert _SENTINEL not in payload, (
            f"PRIVACY VIOLATION: full-data sentinel leaked into LLM payload #{i}"
        )

    # Positive control: the intended payload (schema column names + question) IS
    # present, proving we captured the real generate_code prompt.
    joined = "\n".join(captured)
    assert "region" in joined and "amount" in joined
    assert "What is the total amount by region?" in joined

    # And the run completed on the canned responses.
    with create_db_session() as session:
        ds = session.get(DatasetRow, dataset_id)
        assert ds is not None
    assert isinstance(run_id, str) and run_id
