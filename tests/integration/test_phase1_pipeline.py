"""Phase-1 end-to-end pipeline test — REAL Gemini via .env, production driver.

Uploads the 50,000-row fixture (engineered so a 5-row sample sum is nowhere near
the full-data sum), asks a group-by question, and asserts the returned numbers
equal the INDEPENDENTLY-computed FULL-DATA values — proving the agent computed
on all rows, not a sample.

Skips (never stubs) when no Gemini key is present.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sales_50k.csv"

pytestmark = pytest.mark.usefixtures("_require_llm_key")


def _true_region_sums() -> dict[str, float]:
    df = pd.read_csv(FIXTURE)
    return {str(k): float(v) for k, v in df.groupby("region")["amount"].sum().items()}


def _upload(api_client) -> dict:
    with FIXTURE.open("rb") as f:
        r = api_client.post(
            "/datasets",
            files={"file": ("sales_50k.csv", f, "text/csv")},
        )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_upload_profiles_full_dataset(api_client):
    data = _upload(api_client)
    assert data["row_count"] == 50_000
    assert data["column_count"] == 5
    col_names = {c["name"] for c in data["profile"]["columns"]}
    assert {"region", "product", "amount", "quantity", "date"} <= col_names
    # quality_flags is present (list) — may be empty for this clean fixture.
    assert isinstance(data["profile"]["quality_flags"], list)
    assert len(data["profile"]["sample_rows"]) > 0


def test_analyze_uses_full_data_not_sample(api_client):
    dataset = _upload(api_client)
    dataset_id = dataset["id"]

    r = api_client.post(
        "/runs",
        json={"dataset_id": dataset_id, "question": "What is the total amount by region?"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    # If it failed, surface the error instead of an opaque assertion.
    assert body["status"] == "completed", f"run failed: {body.get('error')}"
    assert body["code"].strip(), "generated code is empty"
    assert body["attempts"] >= 1
    assert body["chart"], "chart spec is empty"
    assert body["chart"].get("data", {}).get("values"), "chart has no embedded data"
    assert body["table"], "summary table is empty"

    true_sums = _true_region_sums()
    # Sanity: the full-data total dwarfs any 5-row sample (which sums to ~10).
    assert sum(true_sums.values()) > 1_000_000

    # Map the returned table into {region: amount}. Find, per row, the region
    # string and the numeric value closest to a true region sum.
    matched: dict[str, float] = {}
    for row in body["table"]:
        region = next(
            (str(v) for v in row.values() if str(v) in true_sums), None
        )
        if region is None:
            continue
        numerics = [
            float(v)
            for v in row.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        if numerics:
            # The per-region total is the numeric closest to the true value.
            matched[region] = min(numerics, key=lambda n: abs(n - true_sums[region]))

    assert set(matched) == set(true_sums), (
        f"table regions {set(matched)} != {set(true_sums)}; table={body['table']}"
    )
    for region, true_val in true_sums.items():
        got = matched[region]
        assert got == pytest.approx(true_val, rel=0.01), (
            f"region {region}: got {got}, expected full-data {true_val} "
            f"(sample would be ~0) — the agent did not use all rows"
        )


def test_run_unknown_dataset_returns_404(api_client):
    r = api_client.post(
        "/runs",
        json={"dataset_id": "does-not-exist", "question": "total amount?"},
    )
    assert r.status_code == 404


def test_run_missing_question_returns_400(api_client):
    # Upload so the dataset exists; omit the question.
    dataset = _upload(api_client)
    r = api_client.post("/runs", json={"dataset_id": dataset["id"], "question": "  "})
    assert r.status_code == 400
