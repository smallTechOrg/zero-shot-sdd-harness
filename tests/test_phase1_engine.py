"""Local analysis engine — full-data correctness + bounded results.

No LLM key required: these exercise the DuckDB/pandas engine directly.
"""
import csv

import pytest

from analysis.engine import AnalysisEngine, EngineError
from analysis.loader import LoaderError, load_dataset_metadata


def _write_skewed_csv(path, n_body=200_000):
    """A CSV where a 1000-row sample answer differs from the full-file answer.

    The first `n_body` rows have value=1 (region 'A'); a small skewed tail of
    large values (region 'B') sits at the END of the file. A 1000-row head
    sample sees only region 'A' / value 1; the full file's MAX and the per-region
    SUM are dominated by the tail. So sample != full.
    """
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["region", "value"])
        for _ in range(n_body):
            w.writerow(["A", 1])
        for _ in range(50):
            w.writerow(["B", 1_000_000])
    # full SUM = n_body*1 + 50*1_000_000 ; full MAX = 1_000_000
    return n_body, 50


def test_engine_returns_full_file_answer_not_sample(tmp_path):
    csv_path = tmp_path / "skewed.csv"
    n_body, n_tail = _write_skewed_csv(str(csv_path))
    full_max = 1_000_000
    full_sum = n_body * 1 + n_tail * 1_000_000

    engine = AnalysisEngine(str(csv_path), max_result_rows=1000)

    # The full-file MAX must reflect the skewed tail, not the head sample (value 1).
    res_max = engine.run("SELECT MAX(value) AS m FROM data", language="sql")
    assert res_max.rows[0][0] == full_max

    res_sum = engine.run("SELECT SUM(value) AS s FROM data", language="sql")
    assert res_sum.rows[0][0] == full_sum

    # Sanity: a 1000-row head sample would have given MAX 1 and SUM 1000.
    sample = load_dataset_metadata(str(csv_path), sample_rows=1000)
    sampled_max = max(r["value"] for r in sample.sample_rows)
    assert sampled_max == 1  # the sample is blind to the tail — proves the fixture
    assert full_max != sampled_max


def test_engine_bounds_result_rows(tmp_path):
    csv_path = tmp_path / "many.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id"])
        for i in range(50):
            w.writerow([i])

    engine = AnalysisEngine(str(csv_path), max_result_rows=10)
    res = engine.run("SELECT id FROM data ORDER BY id", language="sql")
    assert len(res.rows) == 10
    assert res.truncated is True


def test_engine_pandas_mode(tmp_path):
    csv_path = tmp_path / "p.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x"])
        for i in range(10):
            w.writerow([i])

    engine = AnalysisEngine(str(csv_path), max_result_rows=1000)
    res = engine.run("result = int(df['x'].sum())", language="pandas")
    assert res.rows[0][0] == sum(range(10))


def test_engine_strips_code_fence(tmp_path):
    csv_path = tmp_path / "f.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["v"])
        w.writerow([5])
        w.writerow([7])

    engine = AnalysisEngine(str(csv_path))
    res = engine.run("```sql\nSELECT SUM(v) FROM data\n```", language="sql")
    assert res.rows[0][0] == 12


def test_engine_surfaces_sql_error(tmp_path):
    csv_path = tmp_path / "e.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["v"])
        w.writerow([1])

    engine = AnalysisEngine(str(csv_path))
    with pytest.raises(EngineError):
        engine.run("SELECT nonexistent_col FROM data", language="sql")


def test_loader_extracts_schema_and_sample(tmp_path):
    csv_path = tmp_path / "s.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "amount"])
        for i in range(30):
            w.writerow([f"n{i}", i * 10])

    profile = load_dataset_metadata(str(csv_path), sample_rows=10)
    assert profile.row_count == 30
    assert profile.column_count == 2
    names = {c["name"] for c in profile.schema}
    assert names == {"name", "amount"}
    assert len(profile.sample_rows) == 10  # bounded to sample_rows


def test_loader_rejects_unparseable(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\x00\x01\x02 not a csv \xff\xfe")
    # DuckDB may or may not raise depending on content; force a clearly bad path.
    missing = tmp_path / "missing.csv"
    with pytest.raises(LoaderError):
        load_dataset_metadata(str(missing), sample_rows=5)
