"""Profiler unit tests — no LLM key required."""
import pytest

from analyst.profile import profile_csv, MAX_SAMPLE_ROWS


def test_profile_basic(tmp_path):
    p = tmp_path / "d.csv"
    p.write_text("a,b\n1,x\n2,y\n3,z\n")
    prof = profile_csv(str(p))
    assert prof.row_count == 3
    names = [c["name"] for c in prof.schema]
    assert names == ["a", "b"]
    assert len(prof.sample_rows) == 3


def test_profile_caps_sample(tmp_path):
    rows = "\n".join(str(i) for i in range(50))
    p = tmp_path / "big.csv"
    p.write_text("n\n" + rows + "\n")
    prof = profile_csv(str(p))
    assert prof.row_count == 50
    assert len(prof.sample_rows) == MAX_SAMPLE_ROWS


def test_profile_empty_file_raises(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("")
    with pytest.raises(ValueError):
        profile_csv(str(p))


def test_profile_handles_nan(tmp_path):
    p = tmp_path / "n.csv"
    p.write_text("a,b\n1,\n,2\n")
    prof = profile_csv(str(p))
    # NaN must serialize to None (JSON-safe)
    assert prof.sample_rows[0]["b"] is None
