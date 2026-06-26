def test_graph_compiles():
    """Graph compiles without requiring any env vars."""
    from graph.agent import agentic_ai
    assert agentic_ai is not None


def test_graph_has_expected_nodes():
    """Graph must have parse_csv, answer_question, handle_error, finalize."""
    from graph.agent import agentic_ai
    # LangGraph compiled graph exposes graph attribute
    nodes = agentic_ai.get_graph().nodes
    node_names = set(nodes.keys())
    assert "parse_csv" in node_names
    assert "answer_question" in node_names
    assert "handle_error" in node_names
    assert "finalize" in node_names
