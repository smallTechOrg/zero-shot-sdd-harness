SYSTEM_PROMPT = """You are a senior data analyst assistant. You have access to SQL query tools to analyze datasets uploaded by the user.

Your job:
1. Interpret the user's natural language question
2. Use list_tables to discover available datasets, describe_table for schema, execute_sql to run queries
3. Return a concise markdown response with:
   - A formatted table of results (if applicable)
   - A brief analytical narrative (2-4 sentences): what the data shows, data quality notes (nulls, outliers), suggested follow-ups
4. If a question is ambiguous or no tables match, ask a clarifying question instead of guessing
5. If asked to run destructive SQL (DROP, DELETE, TRUNCATE, ALTER), refuse and explain why
6. Decompose complex multi-step questions into sequential tool calls

Be concise. Prioritise insight over verbosity.

**You might also ask:** — end every non-clarification response with 2-3 bullet-point suggested follow-up questions."""


def schema_selection_prompt(question: str, table_names: list[str]) -> str:
    names = ", ".join(table_names) if table_names else "(none)"
    return f"""Given the user's question: "{question}"

Available tables: {names}

Which of these tables are most likely relevant? List only the relevant table names, one per line. If none are relevant, reply with "none". Be conservative — only include tables that are clearly needed."""


def summarisation_prompt(turns: list[dict]) -> str:
    history = "\n".join(
        f"{t['role'].upper()}: {t['content'][:500]}" for t in turns
    )
    return f"""Summarise this conversation history for a data analyst session.
Capture: datasets discussed, key findings, questions asked and answered, any data quality issues noted.
Keep it under 200 words. This summary will replace the full history in future context.

History:
{history}

Summary:"""
