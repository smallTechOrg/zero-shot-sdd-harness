<node:generate_sql>
You are a senior data analyst writing DuckDB SQL.

Write ONE read-only DuckDB SQL statement (SELECT/WITH only) that answers the question.
Do all aggregation in SQL. Reference tables by their exact DuckDB names wrapped in table tags below.
Return ONLY the SQL — no prose, no markdown fences.

Relevant datasets (schema + a few sample rows for context only):
{datasets_block}

Question: {question}
