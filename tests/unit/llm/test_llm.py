import pytest
from data_analyst.llm.token_budget import estimate_tokens, check_budget, build_prompt
from data_analyst.llm.sql_extractor import extract_sql


def test_estimate_tokens_approx():
    text = "a" * 400
    result = estimate_tokens(text)
    assert result == 100  # 400 / 4


def test_estimate_tokens_short():
    result = estimate_tokens("hi")
    assert result >= 1


def test_check_budget_within():
    prompt = "x" * 100
    within, tokens = check_budget(prompt, hard_cap=100)
    assert within is True
    assert tokens == 25


def test_check_budget_exceeded():
    prompt = "x" * 10000
    within, tokens = check_budget(prompt, hard_cap=100)
    assert within is False
    assert tokens == 2500


def test_extract_sql_plain():
    result = extract_sql("SELECT * FROM t")
    assert result == "SELECT * FROM t"


def test_extract_sql_strip_fences():
    result = extract_sql("```sql\nSELECT * FROM t\n```")
    assert result == "SELECT * FROM t"


def test_extract_sql_strip_fences_no_lang():
    result = extract_sql("```\nSELECT COUNT(*) FROM t\n```")
    assert result == "SELECT COUNT(*) FROM t"


def test_extract_sql_rejects_insert():
    with pytest.raises(ValueError):
        extract_sql("INSERT INTO t VALUES (1)")


def test_extract_sql_rejects_drop():
    with pytest.raises(ValueError):
        extract_sql("DROP TABLE t")


def test_extract_sql_rejects_non_sql():
    with pytest.raises(ValueError):
        extract_sql("The answer is 42")


def test_extract_sql_rejects_multi_statement():
    with pytest.raises(ValueError, match="Multi-statement"):
        extract_sql("SELECT 1; DROP TABLE sessions")


def test_build_prompt_contains_question():
    schemas = [{"table_name": "sales", "columns": [{"name": "amount", "type": "DOUBLE"}]}]
    prompt = build_prompt(schemas=schemas, history=[], question="how many rows?")
    assert "how many rows?" in prompt
    assert "sales" in prompt
    assert "amount" in prompt
