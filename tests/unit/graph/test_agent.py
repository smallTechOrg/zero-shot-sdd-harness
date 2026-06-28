def test_graph_compiles():
    """Graph compiles without requiring any env vars."""
    from graph.agent import agentic_ai
    assert agentic_ai is not None


def test_graph_has_analyst_nodes():
    from graph.agent import agentic_ai
    nodes = set(agentic_ai.get_graph().nodes)
    for n in ("plan", "generate_code", "execute_code", "finalize", "handle_error"):
        assert n in nodes, f"missing node {n}"
