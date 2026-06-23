"""Test analyst graph compilation."""


def test_graph_compiles():
    """analyst_graph is compiled and exported from graph.agent."""
    from graph.agent import analyst_graph
    assert analyst_graph is not None


def test_graph_has_expected_nodes():
    """Check that the graph has all required nodes."""
    from graph.agent import analyst_graph
    # LangGraph compiled graph exposes graph.nodes
    node_names = set(analyst_graph.nodes.keys())
    assert "query_planner" in node_names
    assert "sql_executor" in node_names
    assert "response_formatter" in node_names
    assert "audit_logger" in node_names
    assert "handle_error" in node_names
    assert "finalize" in node_names
