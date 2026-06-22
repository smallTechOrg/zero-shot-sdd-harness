from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from analyst.domain.session import ColumnDef, DatasetMeta
from analyst.errors import AnalystError
from analyst.services.query_engine import execute_query, validate_ast


def _make_settings(max_result_rows: int = 1000, query_timeout_s: int = 30):
    settings = MagicMock()
    settings.max_result_rows = max_result_rows
    settings.query_timeout_s = query_timeout_s
    return settings


def _make_dataset(tmp_path, name: str, content: str, fmt: str = "csv") -> DatasetMeta:
    ext = ".json" if fmt == "json" else ".csv"
    f = tmp_path / f"{name}{ext}"
    f.write_text(content)
    return DatasetMeta(
        dataset_id="test-id",
        name=name,
        original_filename=f"{name}{ext}",
        format=fmt,
        columns=[],
        row_count=0,
        size_bytes=len(content),
        file_path=str(f),
        uploaded_at=datetime.now(timezone.utc),
    )


class TestExecuteQuery:
    def test_five_row_csv(self, tmp_path):
        content = "id,name\n1,Alice\n2,Bob\n3,Carol\n4,Dave\n5,Eve\n"
        ds = _make_dataset(tmp_path, "people", content)
        settings = _make_settings()
        result = execute_query("SELECT * FROM people", [ds], settings)
        assert result["row_count"] == 5
        assert result["truncated"] is False
        assert len(result["columns"]) == 2
        assert "id" in result["columns"]
        assert "name" in result["columns"]

    def test_row_cap_truncation(self, tmp_path):
        rows = "\n".join(f"{i},val{i}" for i in range(1, 1003))
        content = f"id,val\n{rows}\n"
        ds = _make_dataset(tmp_path, "big_table", content)
        settings = _make_settings(max_result_rows=1000)
        result = execute_query("SELECT * FROM big_table", [ds], settings)
        assert result["row_count"] == 1000
        assert result["truncated"] is True
        assert result["total_row_count"] == 1002

    def test_unknown_table_raises(self, tmp_path):
        content = "id,val\n1,a\n"
        ds = _make_dataset(tmp_path, "my_table", content)
        settings = _make_settings()
        with pytest.raises(AnalystError) as exc_info:
            execute_query("SELECT * FROM nonexistent_table", [ds], settings)
        assert exc_info.value.code == "unknown_table"
        assert exc_info.value.status_code == 422


class TestTimeoutRaceCondition:
    """Fix 1: conn.interrupt() must be called before conn.close() when thread is alive."""

    def test_timeout_raises_query_timeout_code(self, tmp_path):
        """A query that exceeds the timeout raises AnalystError with code=query_timeout and status=504."""
        content = "id,val\n1,a\n"
        ds = _make_dataset(tmp_path, "slow_table", content)
        # Set a very short timeout (1 s) and use a query that sleeps long enough.
        # DuckDB doesn't have a SLEEP() function, but we can exercise the timeout path
        # by patching the thread so it never finishes.
        import threading
        from unittest.mock import patch

        original_start = threading.Thread.start

        def _make_blocking_start(self_thread):
            """Replace _run with an infinite loop to force the timeout branch."""
            import time

            self_thread._target = lambda: time.sleep(60)
            original_start(self_thread)

        with patch.object(threading.Thread, "start", _make_blocking_start):
            settings = _make_settings(query_timeout_s=1)
            with pytest.raises(AnalystError) as exc_info:
                execute_query("SELECT * FROM slow_table", [ds], settings)

        assert exc_info.value.code == "query_timeout"
        assert exc_info.value.status_code == 504

    def test_timeout_message(self, tmp_path):
        """Timeout error message matches the spec wording."""
        content = "id,val\n1,a\n"
        ds = _make_dataset(tmp_path, "msg_table", content)
        import threading
        from unittest.mock import patch

        original_start = threading.Thread.start

        def _make_blocking_start(self_thread):
            import time
            self_thread._target = lambda: time.sleep(60)
            original_start(self_thread)

        with patch.object(threading.Thread, "start", _make_blocking_start):
            settings = _make_settings(query_timeout_s=1)
            with pytest.raises(AnalystError) as exc_info:
                execute_query("SELECT * FROM msg_table", [ds], settings)

        assert "time limit" in exc_info.value.message.lower()


class TestValidateAst:
    def test_allows_select(self):
        validate_ast("SELECT * FROM foo")  # should not raise

    def test_rejects_drop(self):
        with pytest.raises(AnalystError) as exc_info:
            validate_ast("DROP TABLE foo")
        assert exc_info.value.code == "sql_rejected"
        assert exc_info.value.status_code == 422

    def test_rejects_insert(self):
        with pytest.raises(AnalystError):
            validate_ast("INSERT INTO t VALUES (1)")

    def test_rejects_delete(self):
        with pytest.raises(AnalystError):
            validate_ast("DELETE FROM t")

    def test_rejects_create(self):
        with pytest.raises(AnalystError):
            validate_ast("CREATE TABLE t (id INT)")
