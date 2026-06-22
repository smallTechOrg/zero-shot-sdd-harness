import re

from analyst.domain.session import DatasetMeta
from analyst.errors import AnalystError
from analyst.llm.base import GeminiProvider

_BLOCKLIST_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b",
    re.IGNORECASE,
)


def _extract_sql(response_text: str) -> str:
    """Strip markdown fences (```sql ... ``` or ``` ... ```) and surrounding whitespace."""
    text = response_text.strip()
    # Match ```sql...``` or ```...```
    fenced = re.match(r"^```(?:sql)?\s*\n?(.*?)```$", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return text


def _check_keyword_blocklist(sql: str) -> None:
    """Raise AnalystError if SQL contains any DML/DDL keywords."""
    match = _BLOCKLIST_PATTERN.search(sql)
    if match:
        raise AnalystError(
            "sql_rejected",
            f"SQL contains disallowed keyword: {match.group(0)}",
            422,
        )


def build_schema_text(datasets: list[DatasetMeta]) -> str:
    """Build a human-readable schema description for all datasets."""
    parts = []
    for ds in datasets:
        col_str = ", ".join(f"{c.name} ({c.type})" for c in ds.columns)
        parts.append(f"Table: {ds.name}\nColumns: {col_str}")
    return "\n\n".join(parts)


def build_prompt(system_template: str, schema_text: str, question: str) -> str:
    """Replace {schema} and {question} placeholders in the system template."""
    return system_template.replace("{schema}", schema_text).replace("{question}", question)


def generate_sql_for_question(
    question: str,
    datasets: list[DatasetMeta],
    provider: GeminiProvider,
    system_template: str,
) -> str:
    """Full NL-to-SQL pipeline: validate inputs, build prompt, call provider, validate output."""
    if not datasets:
        raise AnalystError("no_datasets", "Session has no datasets loaded. Upload a dataset before querying.", 422)

    schema_text = build_schema_text(datasets)
    prompt = build_prompt(system_template, schema_text, question)
    raw = provider.generate_sql(prompt)
    sql = _extract_sql(raw)
    _check_keyword_blocklist(sql)
    return sql
