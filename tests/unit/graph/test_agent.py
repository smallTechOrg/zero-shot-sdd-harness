def test_graph_compiles():
    """Graph compiles without requiring any env vars."""
    from graph.agent import agentic_ai
    assert agentic_ai is not None


def test_graph_has_pipeline_nodes():
    from graph.agent import agentic_ai
    nodes = set(agentic_ai.get_graph().nodes.keys())
    for n in ["load_schema", "generate_sql", "execute_sql", "format_answer",
              "handle_error", "finalize"]:
        assert n in nodes
