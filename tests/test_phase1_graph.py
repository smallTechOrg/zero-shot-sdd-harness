"""End-to-end graph runs on the REAL Gemini Flash model (key from .env)."""
import csv

import pytest

from db.models import AnalysisStep, CostRecord, Dataset, Question
from db.session import create_db_session


def _seed_dataset(csv_path, sample_rows=10):
    from analysis.loader import load_dataset_metadata

    profile = load_dataset_metadata(str(csv_path), sample_rows=sample_rows)
    with create_db_session() as s:
        ds = Dataset(
            filename=csv_path.name,
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


def _ask(dataset_id, text):
    with create_db_session() as s:
        q = Question(dataset_id=dataset_id, text=text, status="pending")
        s.add(q)
        s.flush()
        qid = q.id
    from graph.runner import run_question

    run_question(qid)
    return qid


@pytest.mark.usefixtures("_require_llm_key")
def test_graph_end_to_end_real_gemini(tmp_path):
    csv_path = tmp_path / "sales.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "revenue"])
        rows = [("West", 100), ("East", 200), ("West", 300), ("East", 50)]
        for r in rows:
            w.writerow(r)

    ds_id = _seed_dataset(csv_path)
    qid = _ask(ds_id, "What is the total revenue by region, highest first?")

    with create_db_session() as s:
        q = s.get(Question, qid)
        status, answer, plan_json, error_message = (
            q.status,
            q.answer,
            q.plan_json,
            q.error_message,
        )
        steps = [
            {"code": st.code, "result": st.result_json}
            for st in s.query(AnalysisStep).filter_by(question_id=qid).all()
        ]
        cost = s.query(CostRecord).filter_by(question_id=qid).one_or_none()
        cost_vals = (cost.tokens_in, cost.tokens_out, cost.estimated_usd) if cost else None

    assert status == "completed", f"run failed: {error_message}"
    assert answer and len(answer) > 0
    assert plan_json and len(plan_json) >= 1
    assert len(steps) >= 1
    # at least one step ran code and produced a result
    assert any(st["code"] and st["result"] for st in steps)
    assert cost_vals is not None
    assert cost_vals[0] > 0
    assert cost_vals[1] > 0
    assert cost_vals[2] > 0


@pytest.mark.usefixtures("_require_llm_key")
def test_graph_full_data_answer_not_sample(tmp_path):
    """The agent must return the FULL-FILE number, not the 1000-row sample number.

    A skewed tail (region B, large values) sits past the sample window, so a
    sampled answer would be wrong. The agent's locally-run code sees all rows.
    """
    csv_path = tmp_path / "skewed.csv"
    n_body = 200_000
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "value"])
        for _ in range(n_body):
            w.writerow(["A", 1])
        for _ in range(50):
            w.writerow(["B", 1_000_000])

    full_max = 1_000_000
    ds_id = _seed_dataset(csv_path)
    qid = _ask(ds_id, "What is the single largest value in the value column? Report the exact number.")

    with create_db_session() as s:
        q = s.get(Question, qid)
        status, error_message, answer = q.status, q.error_message, q.answer
        step_results = [
            st.result_json
            for st in s.query(AnalysisStep).filter_by(question_id=qid).all()
        ]

    assert status == "completed", f"run failed: {error_message}"

    # The full-file max must appear in the executed step result OR the answer —
    # proving the code ran over all rows, not the head sample (whose max is 1).
    flat_all = str(step_results) + " " + (answer or "")
    assert str(full_max) in flat_all, (
        "agent did not compute the full-file max (1,000,000) — it may have "
        f"answered from the sample. Steps: {step_results}"
    )
