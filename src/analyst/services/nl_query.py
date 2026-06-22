import logging
import re

from analyst.domain.session import DatasetMeta
from analyst.errors import AnalystError
from analyst.llm.base import GeminiProvider

log = logging.getLogger(__name__)

_BLOCKLIST_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b",
    re.IGNORECASE,
)


def _extract_sql(response_text: str) -> str:
    """Strip markdown fences and any surrounding explanation text."""
    text = response_text.strip()
    # Pull out content from ```sql...``` or ```...``` anywhere in the response
    fenced = re.search(r"```(?:sql)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    # If no fences, take only the first SELECT statement line(s)
    lines = text.splitlines()
    sql_lines = []
    in_sql = False
    for line in lines:
        if re.match(r"^\s*SELECT\b", line, re.IGNORECASE):
            in_sql = True
        if in_sql:
            sql_lines.append(line)
    return "\n".join(sql_lines).strip() if sql_lines else text


def _check_keyword_blocklist(sql: str) -> None:
    match = _BLOCKLIST_PATTERN.search(sql)
    if match:
        log.warning("sql_rejected: keyword=%s sql=%r", match.group(0), sql)
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
    log.info("gemini_raw: %r", raw)
    sql = _extract_sql(raw)
    log.info("extracted_sql: %r", sql)
    _check_keyword_blocklist(sql)
    return sql
