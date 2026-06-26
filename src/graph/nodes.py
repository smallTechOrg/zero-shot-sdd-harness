"""Graph nodes for the pandas Q&A pipeline."""
import time
from pathlib import Path

from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from graph.state import AgentState, NodeTrace
from observability.events import get_logger

_log = get_logger("nodes")
_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "answer_question.md"


# ---------------------------------------------------------------------------
# Node trace helpers
# ---------------------------------------------------------------------------

def _enter(state: AgentState, node: str) -> float:
    return time.monotonic()


def _exit(state: AgentState, node: str, t0: float) -> list[NodeTrace]:
    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    existing: list[NodeTrace] = list(state.get("node_trace") or [])
    existing.append(NodeTrace(node=node, duration_ms=duration_ms))
    return existing


# ---------------------------------------------------------------------------
# LLM call with retry
# ---------------------------------------------------------------------------

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_with_retry(prompt: str, *, system: str | None = None):
    """Call Gemini via the google-genai SDK and return a structured response."""
    import time as _time
    from google import genai
    from google.genai import types
    from config.settings import get_settings
    from llm.response import LLMResponse
    from llm.router import get_router

    s = get_settings()
    model_override = get_router().route("tools")

    from llm.providers.gemini import GeminiProvider
    model = model_override or GeminiProvider.DEFAULT_MODEL

    client = genai.Client(api_key=s.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
    ) if system else None

    t0 = _time.monotonic()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    latency_ms = round((_time.monotonic() - t0) * 1000, 2)

    text = response.text or ""
    tokens_in = 0
    tokens_out = 0
    if response.usage_metadata:
        tokens_in = response.usage_metadata.prompt_token_count or 0
        tokens_out = response.usage_metadata.candidates_token_count or 0

    # Rough cost estimate for gemini-2.0-flash: ~$0.075/1M input, ~$0.30/1M output
    cost_usd = (tokens_in * 0.075 + tokens_out * 0.30) / 1_000_000

    return LLMResponse(
        text=text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        model=model,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def parse_csv(state: AgentState) -> AgentState:
    t0 = _enter(state, "parse_csv")
    try:
        df = state.get("dataframe")
        if df is None or len(df) == 0:
            return {
                **state,
                "error": "DataFrame is empty or missing.",
                "node_trace": _exit(state, "parse_csv", t0),
            }
        column_schema = [{"name": col, "dtype": str(df[col].dtype)} for col in df.columns]
        _log.info(
            "csv.parsed",
            run_id=state.get("run_id"),
            session_id=state.get("session_id"),
            row_count=len(df),
            column_count=len(df.columns),
        )
        return {
            **state,
            "column_schema": column_schema,
            "node_trace": _exit(state, "parse_csv", t0),
        }
    except Exception as exc:
        _log.error("node.error", run_id=state.get("run_id"), node="parse_csv", error=str(exc))
        return {**state, "error": str(exc), "node_trace": _exit(state, "parse_csv", t0)}


def answer_question(state: AgentState) -> AgentState:
    t0 = _enter(state, "answer_question")
    try:
        df = state["dataframe"]
        column_schema = state["column_schema"]
        question = state["question"]

        # Build schema text
        schema_lines = [f"  {c['name']} ({c['dtype']})" for c in column_schema]
        schema_text = "\n".join(schema_lines)

        # Build sample rows table (first 10 rows as markdown)
        sample = df.head(10)
        headers = list(sample.columns)
        header_row = " | ".join(headers)
        sep = " | ".join(["---"] * len(headers))
        data_rows = "\n".join(
            "| " + " | ".join(str(sample.iloc[i][h]) for h in headers) + " |"
            for i in range(len(sample))
        )
        sample_table = f"| {header_row} |\n| {sep} |\n{data_rows}"

        # Load system prompt from file
        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8").strip()

        user_prompt = (
            f"Column schema ({len(df)} rows total):\n{schema_text}\n\n"
            f"First {len(sample)} rows:\n{sample_table}\n\n"
            f"Question: {question}"
        )

        response = _call_with_retry(user_prompt, system=system_prompt)

        _log.info(
            "llm.call",
            run_id=state.get("run_id"),
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            cost_usd=response.cost_usd,
        )

        return {
            **state,
            "answer": response.text,
            "tokens_in": (state.get("tokens_in") or 0) + response.tokens_in,
            "tokens_out": (state.get("tokens_out") or 0) + response.tokens_out,
            "cost_usd": (state.get("cost_usd") or 0.0) + response.cost_usd,
            "model": response.model,
            "node_trace": _exit(state, "answer_question", t0),
        }
    except Exception as exc:
        _log.error("node.error", run_id=state.get("run_id"), node="answer_question", error=str(exc))
        return {**state, "error": str(exc), "node_trace": _exit(state, "answer_question", t0)}


def handle_error(state: AgentState) -> AgentState:
    _log.error("handle_error", error=state.get("error"))
    return {**state, "status": "failed"}


def finalize(state: AgentState) -> AgentState:
    return {**state, "status": "completed"}
