import time
from pathlib import Path

from graph.state import AgentState, NodeTrace
from llm.client import LLMClient
from llm.router import get_router
from observability.events import get_logger

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_log = get_logger("nodes")


def _load_prompt(filename: str = "transform.md") -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def _enter(state: AgentState, node: str) -> float:
    _log.info("node.start", run_id=state.get("run_id"), node=node)
    return time.monotonic()


def _exit(state: AgentState, node: str, t0: float) -> list[NodeTrace]:
    duration_ms = round((time.monotonic() - t0) * 1000, 2)
    _log.info("node.end", run_id=state.get("run_id"), node=node, duration_ms=duration_ms)
    trace = list(state.get("node_trace") or [])
    trace.append(NodeTrace(node=node, duration_ms=duration_ms))
    return trace


def transform_text(state: AgentState) -> AgentState:
    t0 = _enter(state, "transform_text")
    try:
        prompt_template = _load_prompt()
        # Route the capability work through the "tools" task. Blank route →
        # provider default (byte-identical to before); set AGENT_MODEL_TOOLS to
        # route this call to a specific tier. The react node (Phase 2) is where
        # routing earns its keep; here it proves the wiring end to end.
        response = LLMClient().call_model(
            f"{prompt_template}\n\nInput: {state['input_text']}",
            model=get_router().route("tools"),
        )
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
            "output_text": response.text,
            "tokens_in": (state.get("tokens_in") or 0) + response.tokens_in,
            "tokens_out": (state.get("tokens_out") or 0) + response.tokens_out,
            "cost_usd": (state.get("cost_usd") or 0.0) + response.cost_usd,
            "model": response.model,
            "node_trace": _exit(state, "transform_text", t0),
        }
    except Exception as exc:
        _log.error("node.error", run_id=state.get("run_id"), node="transform_text", error=str(exc))
        return {**state, "error": str(exc), "node_trace": _exit(state, "transform_text", t0)}


def handle_error(state: AgentState) -> AgentState:
    t0 = _enter(state, "handle_error")
    _log.error("run.failed", run_id=state.get("run_id"), error=state.get("error"))
    return {**state, "status": "failed", "node_trace": _exit(state, "handle_error", t0)}


def finalize(state: AgentState) -> AgentState:
    t0 = _enter(state, "finalize")
    _log.info(
        "run.complete",
        run_id=state.get("run_id"),
        tokens_in=state.get("tokens_in", 0),
        tokens_out=state.get("tokens_out", 0),
        cost_usd=state.get("cost_usd", 0.0),
        model=state.get("model"),
    )
    return {**state, "status": "completed", "node_trace": _exit(state, "finalize", t0)}
