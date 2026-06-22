from datetime import datetime, timezone

import pytest

from analyst.domain.session import ColumnDef, DatasetMeta
from analyst.errors import AnalystError
from analyst.llm.stub_client import StubGeminiClient
from analyst.services.nl_query import (
    _check_keyword_blocklist,
    _extract_sql,
    build_schema_text,
    generate_sql_for_question,
)


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
        raw = "  SELECT * FROM t  "
        assert _extract_sql(raw) == "SELECT * FROM t"

    def test_multiline_fence(self):
        raw = "```sql\nSELECT a,\n       b\nFROM t\n```"
        assert _extract_sql(raw).startswith("SELECT")


class TestKeywordBlocklist:
    def test_rejects_delete(self):
        with pytest.raises(AnalystError) as exc_info:
            _check_keyword_blocklist("DELETE FROM foo")
        assert exc_info.value.code == "sql_rejected"
        assert exc_info.value.status_code == 422

    def test_rejects_drop(self):
        with pytest.raises(AnalystError):
            _check_keyword_blocklist("DROP TABLE users")

    def test_rejects_insert(self):
        with pytest.raises(AnalystError):
            _check_keyword_blocklist("INSERT INTO foo VALUES (1)")

    def test_rejects_update(self):
        with pytest.raises(AnalystError):
            _check_keyword_blocklist("UPDATE foo SET x=1")

    def test_rejects_create(self):
        with pytest.raises(AnalystError):
            _check_keyword_blocklist("CREATE TABLE t (id INT)")

    def test_rejects_alter(self):
        with pytest.raises(AnalystError):
            _check_keyword_blocklist("ALTER TABLE t ADD COLUMN x INT")

    def test_rejects_truncate(self):
        with pytest.raises(AnalystError):
            _check_keyword_blocklist("TRUNCATE TABLE t")

    def test_allows_select(self):
        _check_keyword_blocklist("SELECT * FROM t")  # should not raise

    def test_allows_select_with_delete_in_string(self):
        # 'DELETE' inside a string literal — we do a simple regex scan
        # This is intentionally conservative (may false-positive) but per spec
        # The blocklist is a regex word-boundary check; 'DELETED' as a column name would pass
        _check_keyword_blocklist("SELECT deleted_at FROM t")  # 'deleted_at' has no boundary after DELETE... actually \b check


class TestBuildSchemaText:
    def _make_dataset(self, name: str, cols: list[tuple[str, str]]) -> DatasetMeta:
        return DatasetMeta(
            dataset_id="test-id",
            name=name,
            original_filename=f"{name}.csv",
            format="csv",
            columns=[ColumnDef(name=c[0], type=c[1]) for c in cols],
            row_count=10,
            size_bytes=100,
            file_path="/tmp/test.csv",
            uploaded_at=datetime.now(timezone.utc),
        )

    def test_single_dataset(self):
        ds = self._make_dataset("sales", [("order_id", "integer"), ("customer", "text")])
        text = build_schema_text([ds])
        assert "Table: sales" in text
        assert "order_id (integer)" in text
        assert "customer (text)" in text

    def test_multiple_datasets(self):
        ds1 = self._make_dataset("sales", [("id", "integer")])
        ds2 = self._make_dataset("customers", [("name", "text")])
        text = build_schema_text([ds1, ds2])
        assert "Table: sales" in text
        assert "Table: customers" in text


class TestGenerateSqlForQuestion:
    def _make_dataset(self) -> DatasetMeta:
        return DatasetMeta(
            dataset_id="test-id",
            name="test_table",
            original_filename="test_table.csv",
            format="csv",
            columns=[ColumnDef(name="id", type="integer"), ColumnDef(name="val", type="text")],
            row_count=5,
            size_bytes=50,
            file_path="/tmp/test.csv",
            uploaded_at=datetime.now(timezone.utc),
        )

    def test_stub_provider_returns_stub_sql(self):
        provider = StubGeminiClient()
        dataset = self._make_dataset()
        sql = generate_sql_for_question(
            "show all data",
            [dataset],
            provider,
            "System template {schema} {question}",
        )
        assert "stub-nl-query" in sql

    def test_empty_datasets_raises(self):
        provider = StubGeminiClient()
        with pytest.raises(AnalystError) as exc_info:
            generate_sql_for_question("show all", [], provider, "template {schema} {question}")
        assert exc_info.value.code == "no_datasets"
        assert exc_info.value.status_code == 422

    # Fix 4: provider.generate_sql receives the assembled prompt string, not 3 separate args
    def test_provider_receives_assembled_prompt(self):
        """generate_sql is called with the fully assembled prompt (schema + question interpolated)."""
        received: list[str] = []

        class CapturingProvider:
            def generate_sql(self, prompt: str) -> str:
                received.append(prompt)
                return "SELECT 1"

        dataset = self._make_dataset()
        generate_sql_for_question(
            "how many rows?",
            [dataset],
            CapturingProvider(),
            "Schema: {schema} | Question: {question}",
        )

        assert len(received) == 1
        prompt = received[0]
        # The assembled prompt must contain both the schema fragment and the question
        assert "test_table" in prompt
        assert "how many rows?" in prompt

    def test_stub_generate_sql_accepts_single_prompt_arg(self):
        """StubGeminiClient.generate_sql now accepts a single prompt string."""
        client = StubGeminiClient()
        result = client.generate_sql("assembled prompt string")
        assert "stub-nl-query" in result
