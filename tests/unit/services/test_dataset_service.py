import os
import tempfile

import pytest

from analyst.errors import AnalystError
from analyst.services.dataset_service import _normalise_table_name, infer_schema, validate_file
from analyst.services.nl_query import _extract_sql


class TestNormaliseTableName:
    def test_spaces_hyphens_and_extension(self):
        assert _normalise_table_name("Sales Data Q1-2024.csv") == "sales_data_q1_2024"

    def test_already_clean(self):
        assert _normalise_table_name("sales.csv") == "sales"

    def test_json_extension_stripped(self):
        assert _normalise_table_name("my-data.json") == "my_data"

    def test_multiple_spaces(self):
        assert _normalise_table_name("My File Name.csv") == "my_file_name"


class TestValidateFile:
    def test_accepts_csv(self):
        validate_file("data.csv", 100)  # should not raise

    def test_accepts_json(self):
        validate_file("data.json", 100)  # should not raise

    def test_rejects_xlsx(self):
        with pytest.raises(AnalystError) as exc_info:
            validate_file("data.xlsx", 100)
        assert exc_info.value.code == "unsupported_format"
        assert exc_info.value.status_code == 400

    def test_rejects_oversized_file(self):
        max_bytes = 50 * 1024 * 1024
        with pytest.raises(AnalystError) as exc_info:
            validate_file("data.csv", max_bytes + 1)
        assert exc_info.value.code == "file_too_large"
        assert exc_info.value.status_code == 400

    def test_rejects_txt(self):
        with pytest.raises(AnalystError):
            validate_file("notes.txt", 100)


class TestInferSchema:
    def test_csv_infers_columns(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name,score\n1,Alice,95\n2,Bob,87\n")
        columns, row_count = infer_schema(str(csv_file), "csv")
        assert len(columns) > 0
        col_names = [c.name for c in columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "score" in col_names
        assert row_count == 2

    def test_csv_row_count(self, tmp_path):
        csv_file = tmp_path / "data.csv"
        rows = "\n".join(f"{i},val{i}" for i in range(1, 11))
        csv_file.write_text(f"id,val\n{rows}\n")
        _, row_count = infer_schema(str(csv_file), "csv")
        assert row_count == 10

    # Fix 2: DuckDB errors during schema inference are wrapped in AnalystError("invalid_file", ...)
    def test_malformed_json_raises_invalid_file(self, tmp_path):
        """A JSON file with invalid syntax triggers a DuckDB error wrapped as invalid_file (400)."""
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json at all {{{{")
        with pytest.raises(AnalystError) as exc_info:
            infer_schema(str(bad_json), "json")
        assert exc_info.value.code == "invalid_file"
        assert exc_info.value.status_code == 400
        assert "JSON" in exc_info.value.message

    def test_missing_csv_file_raises_invalid_file(self, tmp_path):
        """A CSV path that no longer exists triggers a DuckDB IO error wrapped as invalid_file (400)."""
        missing_path = str(tmp_path / "gone.csv")
        with pytest.raises(AnalystError) as exc_info:
            infer_schema(missing_path, "csv")
        assert exc_info.value.code == "invalid_file"
        assert exc_info.value.status_code == 400
        assert "CSV" in exc_info.value.message


class TestValidateFileInjection:
    """Fix 3: filenames with quote or path-separator characters are rejected."""

    def test_rejects_single_quote(self):
        with pytest.raises(AnalystError) as exc_info:
            validate_file("my'file.csv", 100)
        assert exc_info.value.code == "invalid_file"
        assert exc_info.value.status_code == 400

    def test_rejects_double_quote(self):
        with pytest.raises(AnalystError) as exc_info:
            validate_file('my"file.csv', 100)
        assert exc_info.value.code == "invalid_file"
        assert exc_info.value.status_code == 400

    def test_rejects_forward_slash(self):
        with pytest.raises(AnalystError) as exc_info:
            validate_file("../etc/passwd.csv", 100)
        assert exc_info.value.code == "invalid_file"
        assert exc_info.value.status_code == 400

    def test_rejects_backslash(self):
        with pytest.raises(AnalystError) as exc_info:
            validate_file("..\\windows\\file.csv", 100)
        assert exc_info.value.code == "invalid_file"
        assert exc_info.value.status_code == 400

    def test_accepts_clean_csv_name(self):
        validate_file("sales_data_2024.csv", 100)  # should not raise

    def test_accepts_clean_json_name(self):
        validate_file("my-data.json", 100)  # should not raise


class TestExtractSql:
    def test_strips_sql_fence(self):
        raw = "```sql\nSELECT * FROM foo\n```"
        assert _extract_sql(raw) == "SELECT * FROM foo"

    def test_strips_plain_fence(self):
        raw = "```\nSELECT 1\n```"
        assert _extract_sql(raw) == "SELECT 1"

    def test_passthrough_plain_sql(self):
        raw = "SELECT id FROM users"
        assert _extract_sql(raw) == "SELECT id FROM users"

    def test_strips_whitespace(self):
        raw = "  SELECT 1  "
        assert _extract_sql(raw) == "SELECT 1"
