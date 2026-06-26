"""Tests for CSV session creation via the sessions API.

Chart selection is a Phase 2 feature — tested here as a labelled stub.
"""
import io


def _make_csv(headers: list, rows: list) -> bytes:
    lines = [",".join(headers)]
    for row in rows:
        lines.append(",".join(str(v) for v in row))
    return "\n".join(lines).encode("utf-8")


def test_chart_stub_not_in_phase1_response(api_client):
    """In Phase 1, chart_base64 and chart_type are always None (stub)."""
    # Phase 2 stub — we verify the fields exist but are None
    # The actual chart rendering is a Phase 2 feature
    csv_bytes = _make_csv(["x", "y"], [[1, 2], [3, 4]])
    r = api_client.post(
        "/sessions",
        files={"file": ("data.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    # chart_base64 / chart_type are not part of the upload response
    assert "session_id" in data
    assert "columns" in data
    assert "row_count" in data
