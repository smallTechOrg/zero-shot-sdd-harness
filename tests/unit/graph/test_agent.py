def test_graph_compiles_without_env():
    """The graph must compile with zero env vars / no network."""
    from data_analyst.graph.agent import compiled_graph

    assert compiled_graph is not None
    assert hasattr(compiled_graph, "invoke")


def test_stub_provider_branches_on_node_tags():
    from data_analyst.llm.providers.stub import StubProvider

    p = StubProvider()
    plan = p.complete("<node:plan> <table>s1_invoices</table>", model="x")
    assert "s1_invoices" in plan and "relevant_tables" in plan

    sql = p.complete("<node:generate_sql> <table>s1_invoices</table>", model="x")
    assert sql.lower().startswith("select")
    assert "s1_invoices" in sql

    summary = p.complete("<node:summarize> <result_preview>123</result_preview>", model="x")
    assert "[stub answer]" in summary
