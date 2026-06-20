import uuid
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from .config import get_settings
from .db import Message, Run, Span, get_sessionmaker
from .graph import build_graph
from .llm import get_model
from .observability import span

DOMAIN_PROMPT = """You are a senior data analyst. Answer the user's analytical questions using the uploaded dataset.

For EVERY question, follow this sequence:
1. Call inspect_data() to understand the schema, columns, and sample data.
2. Call write_todos with a brief plan (one or two steps).
3. Call execute_pandas(code) with a single pandas expression to compute the answer.
   - Use only: df, pd, np, and built-ins (sum, min, max, len, round, etc.)
   - No imports, no open(), no shell access, no assignments — single expressions only.
   - For multi-step analysis, call execute_pandas multiple times.
4. Call finish(answer, chart) with:
   - answer: a clear explanation including the key number(s) and a markdown table when tabular.
   - chart: a Chart.js config JSON string for time-series, comparisons, or distributions; omit (None) for scalar results.

Chart format when included:
{"type":"bar","data":{"labels":["Jan","Feb","Mar"],"datasets":[{"label":"Revenue","data":[45000,38000,52000],"backgroundColor":"rgba(37,99,235,0.7)"}]},"options":{"responsive":true,"plugins":{"legend":{"position":"top"}}}}

Rules:
- Ground every fact in the execute_pandas results — never invent numbers.
- If the dataset is not loaded, say so clearly and ask the user to upload a file.
- If (and only if) the user explicitly shares a durable personal preference, call remember(fact) once.
- Call finish exactly once when done."""


async def _load_prior_messages(session_id: str) -> list:
    from sqlalchemy import select as sa_select, desc
    prior: list = []
    async with get_sessionmaker()() as s:
        runs = (await s.execute(
            sa_select(Run).where(Run.thread_id == session_id)
            .order_by(desc(Run.created_at)).limit(3)
        )).scalars().all()
        for run in reversed(runs):
            msgs = (await s.execute(
                sa_select(Message).where(Message.run_id == run.id)
                .order_by(Message.created_at)
            )).scalars().all()
            for m in msgs:
                if m.role == "assistant":
                    prior.append(AIMessage(content=m.content))
                elif m.role == "human":
                    prior.append(HumanMessage(content=m.content))
    return prior


async def _build_seed(goal: str, run_id: str, session_id: str | None) -> dict:
    """Initial graph state: domain prompt + long-term memory + prior turns + the new goal."""
    prior = await _load_prior_messages(session_id) if session_id else []
    from .memory import recall_text
    mem = await recall_text()
    sys_prompt = DOMAIN_PROMPT + (f"\n\nKnown facts remembered across sessions:\n{mem}" if mem else "")
    return {"messages": [SystemMessage(content=sys_prompt)] + prior + [HumanMessage(content=goal)],
            "iterations": 0, "answer": None, "chart": None, "run_id": run_id}


async def run_agent(goal: str, model=None, run_id: str | None = None,
                    session_id: str | None = None, checkpointer=None, approve: bool = False) -> dict:
    settings = get_settings()
    run_id = run_id or uuid.uuid4().hex
    model = model or get_model()

    async with get_sessionmaker()() as s:
        s.add(Run(id=run_id, goal=goal, status="running", iterations=0, thread_id=session_id))
        await s.commit()

    graph = build_graph(model)
    config = {"recursion_limit": 50}
    state = await _build_seed(goal, run_id, session_id)

    from .sessions import current_session_id
    from .guardrails import hitl_approved, scan_pii
    token = current_session_id.set(session_id)
    htoken = hitl_approved.set(approve)
    try:
        async with span(run_id, "invoke_agent", "INTERNAL", goal=goal):
            result = await graph.ainvoke(state, config=config)
    finally:
        current_session_id.reset(token)
        hitl_approved.reset(htoken)

    _v = scan_pii(result["answer"])              # guardrail: mask PII before it leaves the system
    if _v.action == "transform":
        result["answer"] = _v.payload
    elif _v.action == "block":
        result["answer"] = "[response withheld: contained sensitive data]"

    async with get_sessionmaker()() as s:
        for m in result["messages"]:
            role = "assistant" if isinstance(m, AIMessage) else getattr(m, "type", "system")
            content = m.content if isinstance(m.content, str) else str(m.content)
            s.add(Message(id=uuid.uuid4().hex, run_id=run_id, role=role, content=content))
        spans = (await s.execute(select(Span).where(Span.run_id == run_id, Span.kind == "LLM"))).scalars().all()
        tok_in = sum((sp.attributes or {}).get("tokens", {}).get("input", 0) for sp in spans)
        tok_out = sum((sp.attributes or {}).get("tokens", {}).get("output", 0) for sp in spans)
        run = (await s.execute(select(Run).where(Run.id == run_id))).scalar_one()
        run.status, run.answer, run.iterations = "completed", result["answer"], result["iterations"]
        run.input_tokens, run.output_tokens = tok_in, tok_out
        run.cost_usd = (tok_in * settings.price_in + tok_out * settings.price_out) / 1_000_000
        await s.commit()

    return {"run_id": run_id, "session_id": session_id, "thread_id": session_id,
            "status": "completed", "answer": result["answer"], "chart": result.get("chart"),
            "iterations": result["iterations"],
            "input_tokens": tok_in, "output_tokens": tok_out,
            "cost_usd": (tok_in * settings.price_in + tok_out * settings.price_out) / 1_000_000,
            "messages": result["messages"]}


async def stream_agent(goal: str, *, model=None, session_id: str | None = None,
                       run_id: str | None = None):
    """Stream a run's progress over SSE: a 'step' event per node, then a 'done' event with the
    answer. A view over the same loop as run_agent (the canonical persisted path is POST /runs)."""
    from .sessions import current_session_id
    run_id = run_id or uuid.uuid4().hex
    model = model or get_model()
    graph = build_graph(model)
    state = await _build_seed(goal, run_id, session_id)
    token = current_session_id.set(session_id)
    try:
        async for chunk in graph.astream(state, config={"recursion_limit": 50}):
            for node, update in chunk.items():
                if node == "finalize":
                    yield {"event": "done", "run_id": run_id, "answer": (update or {}).get("answer", "")}
                else:
                    yield {"event": "step", "node": node}
    finally:
        current_session_id.reset(token)
