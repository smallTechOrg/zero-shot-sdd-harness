"""Privacy boundary — the hard guarantee that no raw cell value reaches the LLM.

Runs a REAL end-to-end agent run (real Gemini via AGENT_GEMINI_API_KEY) on a CSV
that contains a unique sentinel raw value, while capturing EVERY outbound LLM
payload. Asserts the sentinel appears in NONE of them.
"""
import pandas as pd
import pytest

from analysis import profiler
from analysis.dataset_store import get_dataset_store
from db.models import RunRow, DatasetRow
from db.session import create_db_session
import json

SENTINEL = "ZZ_SENTINEL_9137"


@pytest.fixture
def captured_payloads(monkeypatch):
    """Wrap GeminiProvider.generate to record every outbound prompt + system."""
    payloads: list[str] = []
    from llm.providers.gemini import GeminiProvider

    real = GeminiProvider.generate

    def _wrapped(self, prompt, *, system=None, json_mode=False):
        payloads.append(prompt or "")
        if system:
            payloads.append(system)
        return real(self, prompt, system=system, json_mode=json_mode)

    monkeypatch.setattr(GeminiProvider, "generate", _wrapped)
    return payloads


def _seed_dataset(df: pd.DataFrame) -> tuple[str, dict]:
    prof = profiler.profile(df)
    with create_db_session() as session:
        ds = DatasetRow(
            name="sentinel.csv",
            file_path="/tmp/sentinel.csv",
            row_count=len(df),
            col_count=df.shape[1],
            profile_json=json.dumps(prof),
            size_bytes=1,
        )
        session.add(ds)
        session.flush()
        dataset_id = ds.id
    get_dataset_store().put(dataset_id, df)
    return dataset_id, prof


@pytest.mark.usefixtures("_require_llm_key")
def test_privacy_boundary(_isolated_db, captured_payloads):
    # A dataset whose raw rows contain a unique sentinel customer name.
    df = pd.DataFrame(
        {
            "customer": [SENTINEL, "Acme Corp", "Globex", "Initech", "Umbrella"],
            "region": ["North", "South", "North", "South", "East"],
            "sales": [100, 200, 300, 400, 500],
        }
    )
    # Sanity: the sentinel really is in the raw data.
    assert df["customer"].isin([SENTINEL]).any()

    dataset_id, prof = _seed_dataset(df)
    # And the profile (which IS allowed past the gate) must not echo the sentinel.
    assert SENTINEL not in json.dumps(prof)

    with create_db_session() as session:
        run = RunRow(dataset_id=dataset_id, question="What were total sales by region?")
        session.add(run)
        session.flush()
        run_id = run.id

    from graph.runner import run_to_completion

    result = run_to_completion(
        run_id=run_id,
        dataset_id=dataset_id,
        question="What were total sales by region?",
        profile=prof,
    )

    # The run actually used the LLM (payloads were captured).
    assert captured_payloads, "no LLM payloads were captured — agent did not call Gemini"
    assert result["status"] in ("completed", "needs_clarification")

    # THE GUARANTEE: the sentinel raw value appears in NO outbound LLM payload.
    for i, body in enumerate(captured_payloads):
        assert SENTINEL not in body, (
            f"raw sentinel value leaked into LLM payload #{i}:\n{body[:500]}"
        )
