import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from data_analyst.agent.tools import TurnState
from data_analyst.agent.prompts import SYSTEM_PROMPT, schema_selection_prompt, summarisation_prompt
from data_analyst.config.settings import get_settings
from data_analyst.db.models import Session as SessionModel, ConversationTurn, AuditLog, Dataset
from data_analyst.duckdb_service import DuckDBService

logger = logging.getLogger(__name__)


@dataclass
class TurnResult:
    session_id: str
    response_markdown: str
    generated_sql: str | None
    datasets_touched: list[str]
    row_count_returned: int | None
    latency_ms: int


def run_turn(
    session_id: str | None,
    message: str,
    db: Session,
    duckdb_svc: DuckDBService,
    settings=None,
) -> TurnResult:
    """Execute one conversation turn: load context, call Gemini, persist, return result."""
    if settings is None:
        settings = get_settings()

    start_ms = time.time() * 1000

    # Step 1: Get or create session
    session = _get_or_create_session(session_id, db)
    session_id = session.id

    # Step 2: Load active datasets
    datasets = db.query(Dataset).filter(Dataset.is_active == True).all()  # noqa: E712

    # Step 3: Select relevant schemas
    relevant_schemas = _select_relevant_schemas(message, datasets, settings)

    # Step 4: Build schema context for system prompt augmentation
    schema_context = _format_schemas(relevant_schemas) if relevant_schemas else ""

    # Step 5: Load conversation history (sliding window)
    history = _load_history_window(db, session_id, settings)

    # Step 6: Augment system prompt with schema context
    system_with_schema = SYSTEM_PROMPT
    if schema_context:
        system_with_schema += f"\n\n## Available Dataset Schemas\n{schema_context}"

    # Step 7: Run the tool-use loop
    state = TurnState(
        session_id=session_id,
        datasets=datasets,
        duckdb_svc=duckdb_svc,
    )

    from data_analyst.agent.loop import gemini_tool_loop
    response_text = gemini_tool_loop(
        history=history,
        user_message=message,
        state=state,
        settings=settings,
        system_prompt=system_with_schema,
    )

    # Step 8: Compute turn index and save turns to DB
    turn_count = db.query(ConversationTurn).filter(
        ConversationTurn.session_id == session_id
    ).count()

    db.add(ConversationTurn(
        session_id=session_id,
        role="user",
        content=message,
        turn_index=turn_count,
    ))
    db.add(ConversationTurn(
        session_id=session_id,
        role="assistant",
        content=response_text,
        turn_index=turn_count + 1,
    ))

    # Update session last_active
    session.last_active = datetime.now(timezone.utc)

    # Step 9: Write audit log
    end_ms = time.time() * 1000
    latency_ms = int(end_ms - start_ms)

    generated_sql = state.sql_calls[-1] if state.sql_calls else None
    datasets_touched = sorted(state.tables_touched)

    if state.sql_calls:  # only write audit log when SQL was actually executed
        _write_audit_log(
            db,
            session_id,
            message,
            generated_sql,
            datasets_touched,
            state.row_count_returned,
            latency_ms,
        )

    # Step 10: Maybe summarise if too many turns
    _maybe_summarise(db, session_id, settings)

    db.commit()

    return TurnResult(
        session_id=session_id,
        response_markdown=response_text,
        generated_sql=generated_sql,
        datasets_touched=datasets_touched,
        row_count_returned=state.row_count_returned if state.sql_calls else None,
        latency_ms=latency_ms,
    )


def _get_or_create_session(session_id: str | None, db: Session) -> SessionModel:
    """Load an existing session or create a new one."""
    if session_id:
        s = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if s:
            return s
    s = SessionModel()
    db.add(s)
    db.flush()
    return s


def _select_relevant_schemas(message: str, datasets: list, settings) -> list:
    """Use a quick Gemini call to pick relevant tables, or fall back to all if few."""
    if not datasets:
        return []
    if len(datasets) <= 5:
        return datasets

    table_names = [d.table_name for d in datasets]

    from google import genai
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = schema_selection_prompt(message, table_names)

    try:
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=prompt,
        )
        text = response.text.strip().lower()
        if "none" in text:
            return []
        selected = set()
        for line in text.splitlines():
            line = line.strip().strip("-").strip()
            for d in datasets:
                if d.table_name.lower() == line.lower():
                    selected.add(d.table_name)
        if selected:
            return [d for d in datasets if d.table_name in selected]
        # Fall back to first 5 if nothing matched
        logger.warning("Schema selection returned no matches; falling back to first 5 datasets")
        return datasets[:5]
    except Exception as e:
        logger.warning("Schema selection failed, using all datasets: %s", e)
        return datasets[:5]


def _format_schemas(datasets: list) -> str:
    """Format dataset schemas as a compact string for the system prompt."""
    parts = []
    for d in datasets:
        schema = json.loads(d.schema_json) if d.schema_json else []
        # schema is [{column, dtype}] from upload infer_schema
        cols = ", ".join(
            f"{c.get('column', c.get('name', '?'))} ({c.get('dtype', '?')})"
            for c in schema
        ) if schema else "unknown"
        parts.append(f"**{d.table_name}** ({d.row_count} rows): {cols}")
    return "\n".join(parts)


def _load_history_window(db: Session, session_id: str, settings) -> list[dict]:
    """Load the last N non-summarised turns, prepended with summary if present."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()

    turns = (
        db.query(ConversationTurn)
        .filter(
            ConversationTurn.session_id == session_id,
            ConversationTurn.is_summarised == False,  # noqa: E712
        )
        .order_by(ConversationTurn.turn_index)
        .all()
    )

    # Keep only the last max_history_turns turns
    window = turns[-settings.max_history_turns:]

    history = []
    if session and session.summary:
        history.append({
            "role": "assistant",
            "content": f"[Previous conversation summary: {session.summary}]",
        })

    history.extend({"role": t.role, "content": t.content} for t in window)
    return history


def _write_audit_log(
    db: Session,
    session_id: str,
    question: str,
    generated_sql: str | None,
    datasets_touched: list[str],
    row_count: int | None,
    latency_ms: int,
) -> None:
    """Write an audit log entry; failures are logged but non-fatal."""
    try:
        entry = AuditLog(
            session_id=session_id,
            user_question=question,
            generated_sql=generated_sql,
            datasets_touched=json.dumps(datasets_touched),
            row_count_returned=row_count,
            latency_ms=latency_ms,
        )
        db.add(entry)
    except Exception as e:
        logger.error("Failed to write audit log entry: %s", e)


def _maybe_summarise(db: Session, session_id: str, settings) -> None:
    """Summarise history when turn count exceeds max_history_turns."""
    turns = (
        db.query(ConversationTurn)
        .filter(
            ConversationTurn.session_id == session_id,
            ConversationTurn.is_summarised == False,  # noqa: E712
        )
        .order_by(ConversationTurn.turn_index)
        .all()
    )

    if len(turns) <= settings.max_history_turns:
        return

    # Turns to summarise (all except the last summary_keep_turns)
    to_summarise = turns[:-settings.summary_keep_turns]
    if not to_summarise:
        return

    turns_data = [{"role": t.role, "content": t.content} for t in to_summarise]

    from google import genai
    s = get_settings()
    client = genai.Client(api_key=s.gemini_api_key)

    prompt = summarisation_prompt(turns_data)

    try:
        response = client.models.generate_content(model=s.llm_model, contents=prompt)
        summary_text = response.text.strip()
    except Exception as e:
        logger.warning("Summarisation failed: %s", e)
        return

    # Mark turns as summarised
    for t in to_summarise:
        t.is_summarised = True

    # Update session summary
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session:
        existing = session.summary or ""
        # Append to existing summary if present
        session.summary = summary_text if not existing else f"{existing}\n\n{summary_text}"
