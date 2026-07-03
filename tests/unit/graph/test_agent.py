"""Graph structure tests — no network, no env vars required."""


def test_graph_compiles():
    from graph.agent import agentic_ai
    assert agentic_ai is not None


def test_graph_has_all_six_nodes():
    from graph.agent import agentic_ai

    nodes = set(agentic_ai.get_graph().nodes)
    expected = {
        "load_context",
        "generate_code",
        "execute_code",
        "write_answer",
        "finalize",
        "handle_error",
    }
    assert expected <= nodes, f"missing nodes: {expected - nodes}"


def test_import_makes_no_network_call():
    """Importing the graph module must not construct an LLM client / hit the
    network — the graph compiles lazily w.r.t. provider keys."""
    import importlib

    import graph.agent as agent_mod
    importlib.reload(agent_mod)
    assert agent_mod.agentic_ai is not None


def test_edges_bounded_retry_logic():
    from graph.edges import after_execute, after_generate, after_load, after_answer
    from config.settings import get_settings

    max_retries = get_settings().max_code_retries

    # exec_error with attempts remaining → retry.
    assert after_execute({"exec_error": "boom", "attempts": 1}) == "generate_code"
    # exec_error at the retry ceiling → give up.
    assert after_execute({"exec_error": "boom", "attempts": max_retries}) == "handle_error"
    # no exec_error → move on.
    assert after_execute({"exec_error": None}) == "write_answer"

    assert after_load({"error": "x"}) == "handle_error"
    assert after_load({}) == "generate_code"
    assert after_generate({"error": "x"}) == "handle_error"
    assert after_generate({}) == "execute_code"
    assert after_answer({"error": "x"}) == "handle_error"
    assert after_answer({}) == "finalize"
