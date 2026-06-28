"""Privacy boundary — the LLM payload never contains full data rows.

We capture every prompt + system string passed to the provider during a real
run and assert that a sentinel value present ONLY beyond the sample window never
appears in anything sent to the model.
"""
import csv

import pytest

import llm.client as client_module
from db.models import Dataset, Question
from db.session import create_db_session


SENTINEL = "ZZZ_SECRET_ROW_VALUE_9182734"


def _make_dataset(tmp_path, sample_rows=10):
    """CSV whose sentinel appears only AFTER the sample window."""
    csv_path = tmp_path / "priv.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "amount"])
        for i in range(sample_rows):
            w.writerow([f"safe_{i}", i])
        # sentinel rows live well past the sample window
        for i in range(5000):
            w.writerow([SENTINEL, 1])
    from analysis.loader import load_dataset_metadata

    profile = load_dataset_metadata(str(csv_path), sample_rows=sample_rows)
    with create_db_session() as s:
        ds = Dataset(
            filename="priv.csv",
            path=str(csv_path),
            format="csv",
            row_count=profile.row_count,
            column_count=profile.column_count,
            schema_json=profile.schema,
            sample_rows_json=profile.sample_rows,
        )
        s.add(ds)
        s.flush()
        ds_id = ds.id
    return ds_id, profile


@pytest.mark.usefixtures("_require_llm_key")
def test_llm_payload_never_contains_full_data_rows(tmp_path, monkeypatch):
    ds_id, profile = _make_dataset(tmp_path)
    # confirm the fixture: sentinel is NOT in the stored sample rows
    assert all(SENTINEL not in str(r) for r in profile.sample_rows)

    captured: list[str] = []
    real = client_module.LLMClient.call_model_with_usage

    def spy(self, prompt, *, system=None):
        captured.append(prompt or "")
        captured.append(system or "")
        return real(self, prompt, system=system)

    monkeypatch.setattr(client_module.LLMClient, "call_model_with_usage", spy)

    with create_db_session() as s:
        q = Question(dataset_id=ds_id, text="What is the total amount?", status="pending")
        s.add(q)
        s.flush()
        qid = q.id

    from graph.runner import run_question

    run_question(qid)

    assert captured, "expected at least one LLM call to be captured"
    joined = "\n".join(captured)
    assert SENTINEL not in joined, "full data row leaked into an LLM prompt"
