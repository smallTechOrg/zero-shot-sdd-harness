"""Cost guard — the step cap holds and warns instead of looping freely.

Drives the graph deterministically (the LLM is stubbed here to force a plan that
never completes) so we can assert the cap mechanism itself, independent of model
behaviour. The real-Gemini path is covered in test_phase1_graph.py.
"""
import csv

import pytest

from db.models import AnalysisStep, Dataset, Question
from db.session import create_db_session


def _seed(tmp_path):
    csv_path = tmp_path / "c.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["v"])
        for i in range(5):
            w.writerow([i])
    from analysis.loader import load_dataset_metadata

    profile = load_dataset_metadata(str(csv_path), sample_rows=5)
    with create_db_session() as s:
        ds = Dataset(
            filename="c.csv",
            path=str(csv_path),
            format="csv",
            row_count=profile.row_count,
            column_count=profile.column_count,
            schema_json=profile.schema,
            sample_rows_json=profile.sample_rows,
        )
        s.add(ds)
        s.flush()
        return ds.id


class _NeverCompleteClient:
    """Plan with multiple steps; replan always asks for another step."""

    def __init__(self):
        self._call = 0

    def call_model_with_usage(self, prompt, *, system=None):
        self._call += 1
        sys = system or ""
        if "draft a short, ordered analysis plan" in sys.lower():
            import json

            return (
                json.dumps(
                    {
                        "plan": ["step1", "step2", "step3", "step4", "step5", "step6"],
                        "language": "sql",
                        "code": "SELECT SUM(v) AS s FROM data",
                    }
                ),
                10,
                5,
            )
        if "decide whether the plan needs another step" in sys.lower():
            import json

            return (
                json.dumps(
                    {"plan_complete": False, "language": "sql", "code": "SELECT SUM(v) AS s FROM data"}
                ),
                10,
                5,
            )
        # synthesize
        import json

        return (
            json.dumps(
                {
                    "answer": "best effort",
                    "key_numbers": [{"label": "sum", "value": "10"}],
                    "result_table": {"columns": ["s"], "rows": [[10]]},
                }
            ),
            10,
            5,
        )


def test_step_cap_holds_and_warns(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MAX_STEPS", "3")
    import config.settings as cs

    cs._settings = None  # force re-read of AGENT_MAX_STEPS

    ds_id = _seed(tmp_path)

    import graph.nodes as nodes_module

    monkeypatch.setattr(nodes_module, "LLMClient", _NeverCompleteClient)

    with create_db_session() as s:
        q = Question(dataset_id=ds_id, text="sum it many ways", status="pending")
        s.add(q)
        s.flush()
        qid = q.id

    from graph.runner import run_question

    run_question(qid)

    with create_db_session() as s:
        q = s.get(Question, qid)
        status = q.status
        warning = q.cost_guard_warning
        step_count = s.query(AnalysisStep).filter_by(question_id=qid).count()

    assert status == "completed"
    # never exceeds the cap; cap reached exactly
    assert step_count == 3
    assert warning, "cost_guard_warning must be set when the cap is hit"
    assert "step limit" in warning.lower()
