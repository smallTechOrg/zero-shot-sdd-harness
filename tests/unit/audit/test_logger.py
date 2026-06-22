import json
import pytest
from pathlib import Path
from data_analyst.audit.logger import AuditLogger


def test_write_produces_valid_jsonl(tmp_path):
    logger = AuditLogger(tmp_path)
    logger.log("file_upload", "session-1", {"filename": "test.csv", "row_count": 5})
    audit_file = tmp_path / "audit.jsonl"
    assert audit_file.exists()
    line = audit_file.read_text().strip()
    entry = json.loads(line)
    assert entry["event_type"] == "file_upload"
    assert entry["session_id"] == "session-1"
    assert entry["payload"]["filename"] == "test.csv"
    assert "timestamp" in entry


def test_read_recent_reverse_order(tmp_path):
    logger = AuditLogger(tmp_path)
    for i in range(5):
        logger.log("event", "s1", {"i": i})
    entries = logger.read_recent(session_id="s1")
    assert len(entries) == 5
    # Most recent first — last written has i=4
    assert entries[0]["payload"]["i"] == 4
    assert entries[-1]["payload"]["i"] == 0


def test_read_recent_filter_by_session(tmp_path):
    logger = AuditLogger(tmp_path)
    logger.log("event", "s1", {"x": 1})
    logger.log("event", "s2", {"x": 2})
    logger.log("event", "s1", {"x": 3})
    entries_s1 = logger.read_recent(session_id="s1")
    assert len(entries_s1) == 2
    assert all(e["session_id"] == "s1" for e in entries_s1)


def test_log_failure_does_not_raise(tmp_path):
    # Use a path that cannot be created (a file as parent)
    bad_parent = tmp_path / "not_a_dir.txt"
    bad_parent.write_text("blocking")
    logger = AuditLogger(bad_parent)  # parent is a file, not a dir
    # Should not raise
    logger.log("event", "s1", {"x": 1})


def test_token_usage_written(tmp_path):
    logger = AuditLogger(tmp_path)
    logger.log("llm_call", "s1", {"q": "test"}, token_usage={"input": 100, "output": 50})
    entries = logger.read_recent()
    assert entries[0]["token_usage"]["input"] == 100
