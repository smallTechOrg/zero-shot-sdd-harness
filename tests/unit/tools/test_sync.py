"""Unit tests for the 5-stage sync pipeline (stub mode): generation of tools/resources/prompts,
version bump, soft-delete of dropped capabilities, and stub coverage of every stage tag."""
import datetime as _dt

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_analysis_agent.db.models import Base, McpPromptRow, McpResourceRow, McpServerRow, McpToolRow
from data_analysis_agent.tools.sync import (
    ValidationError,
    add_prompt,
    add_resource,
    add_tool,
    apply_sync_result,
    run_sync,
    update_tool,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/sync.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    monkeypatch.setenv("DATAANALYSIS_OPENROUTER_API_KEY", "")
    import data_analysis_agent.llm.client as llm_module
    llm_module._client = None
    yield
    llm_module._client = None


def _server(db, tmp_path, name="sales") -> McpServerRow:
    pq = tmp_path / "orders.parquet"
    pd.DataFrame({"id": [1, 2, 3], "amount": [5, 7, 3]}).to_parquet(pq)
    srv = McpServerRow(name=name, type="parquet", uri=f"parquet:///{name}")
    srv.physical_tables = [{"table_name": "orders", "parquet_path": str(pq),
                            "column_names": ["id", "amount"],
                            "schema": [{"name": "id", "dtype": "int64", "nullable": False}],
                            "row_count": 3}]
    db.add(srv)
    db.flush()
    return srv


def _active(db, model, server_id):
    return db.query(model).filter_by(server_id=server_id, deleted_at=None).all()


def test_run_sync_generates_capabilities(db, tmp_path):
    srv = _server(db, tmp_path)
    apply_sync_result(db, srv, run_sync(db, srv))
    db.commit()
    assert srv.version == 2 and srv.title and srv.description
    assert srv.last_sync_status == "ok"
    tools = _active(db, McpToolRow, srv.id)
    resources = _active(db, McpResourceRow, srv.id)
    prompts = _active(db, McpPromptRow, srv.id)
    assert len(tools) >= 1 and len(prompts) >= 1
    assert any(r.kind == "schema" for r in resources)   # the dataset schema resource
    # the generated tool's SQL must compile (validated at apply)
    assert all(t.sql_template.upper().startswith("SELECT") for t in tools)


def test_resync_soft_deletes_dropped_tool(db, tmp_path):
    srv = _server(db, tmp_path)
    apply_sync_result(db, srv, run_sync(db, srv))
    db.commit()
    # Inject an extra active tool the next sync won't propose; it must be SOFT-deleted, not removed.
    orphan = McpToolRow(server_id=srv.id, name="orphan_tool", description="x",
                        sql_template="SELECT 1", created_version=srv.version)
    db.add(orphan)
    db.commit()
    apply_sync_result(db, srv, run_sync(db, srv))
    db.commit()
    refreshed = db.get(McpToolRow, orphan.id)
    assert refreshed.deleted_at is not None        # soft-deleted (never hard-deleted)
    assert db.get(McpToolRow, orphan.id) is not None  # row still exists


def _synced(db, tmp_path):
    srv = _server(db, tmp_path)
    apply_sync_result(db, srv, run_sync(db, srv))
    db.commit()
    return srv


def _tombstoned(db, model, server_id):
    return db.query(model).filter(model.server_id == server_id, model.deleted_at.isnot(None)).count()


_OK_TOOL = {"name": "top_orders", "description": "top",
            "sql_template": "SELECT * FROM orders LIMIT 5",
            "input_schema": {"type": "object", "properties": {}}}


def test_add_tool_cascades_prompts_additively(db, tmp_path):
    srv = _synced(db, tmp_path)
    v0 = srv.version
    add_tool(db, srv, _OK_TOOL)
    db.commit()
    assert srv.version == v0 + 1
    tools = {t.name for t in _active(db, McpToolRow, srv.id)}
    assert "top_orders" in tools and "list_orders" in tools          # additive: old tool kept
    prompts = {p.name for p in _active(db, McpPromptRow, srv.id)}
    assert "explore_top_orders" in prompts                            # cascaded prompt for the new tool
    assert _tombstoned(db, McpToolRow, srv.id) == 0                   # cascade never soft-deletes
    assert _tombstoned(db, McpPromptRow, srv.id) == 0


def test_add_tool_single_version_bump(db, tmp_path):
    srv = _synced(db, tmp_path)
    v0 = srv.version
    add_tool(db, srv, _OK_TOOL)
    db.commit()
    assert srv.version == v0 + 1
    tool = next(t for t in _active(db, McpToolRow, srv.id) if t.name == "top_orders")
    prompt = next(p for p in _active(db, McpPromptRow, srv.id) if p.name == "explore_top_orders")
    assert tool.created_version == srv.version == prompt.created_version  # one version across add+cascade


def test_add_tool_rejects_active_duplicate(db, tmp_path):
    srv = _synced(db, tmp_path)
    add_tool(db, srv, _OK_TOOL)
    db.commit()
    with pytest.raises(ValidationError):
        add_tool(db, srv, _OK_TOOL)        # duplicate active name
    db.rollback()


def test_update_tool_requires_existing(db, tmp_path):
    srv = _synced(db, tmp_path)
    with pytest.raises(ValidationError):
        update_tool(db, srv, {"name": "does_not_exist", "sql_template": "SELECT 1"})
    db.rollback()


def test_add_tool_rejects_bad_sql(db, tmp_path):
    srv = _synced(db, tmp_path)
    for bad in (
        {"name": "a", "sql_template": "DELETE FROM orders"},                    # non-SELECT
        {"name": "b", "sql_template": "SELECT 1; DROP TABLE orders"},           # multi-statement
        {"name": "c", "sql_template": "SELECT * FROM orders WHERE id > $x"},    # undeclared $param
    ):
        with pytest.raises(ValidationError):
            add_tool(db, srv, bad)
        db.rollback()


def test_add_prompt_has_no_cascade(db, tmp_path):
    srv = _synced(db, tmp_path)
    tools_before = {t.name for t in _active(db, McpToolRow, srv.id)}
    add_prompt(db, srv, {"name": "my_custom", "description": "mine"})
    db.commit()
    assert "my_custom" in {p.name for p in _active(db, McpPromptRow, srv.id)}
    assert {t.name for t in _active(db, McpToolRow, srv.id)} == tools_before  # tools untouched


def test_cascade_preserves_manually_added_prompt(db, tmp_path):
    srv = _synced(db, tmp_path)
    add_prompt(db, srv, {"name": "my_custom", "description": "mine"})
    db.commit()
    add_tool(db, srv, _OK_TOOL)            # cascades prompts (additively)
    db.commit()
    prompts = {p.name for p in _active(db, McpPromptRow, srv.id)}
    assert "my_custom" in prompts          # additive cascade must NOT soft-delete a manual prompt
    assert "explore_top_orders" in prompts


def test_add_resource_bumps_version_and_keeps_siblings(db, tmp_path):
    srv = _synced(db, tmp_path)
    v0 = srv.version
    tools_before = {t.name for t in _active(db, McpToolRow, srv.id)}
    add_resource(db, srv, {"uri": "entity://sales/foo", "name": "foo", "kind": "primary_entity"})
    db.commit()
    assert srv.version == v0 + 1
    assert "entity://sales/foo" in {r.uri for r in _active(db, McpResourceRow, srv.id)}
    # a pure entity (no physical table) adds no tool, and the cascade never drops existing tools
    assert {t.name for t in _active(db, McpToolRow, srv.id)} == tools_before
    assert _tombstoned(db, McpToolRow, srv.id) == 0


def test_stub_handles_all_node_tags():
    from data_analysis_agent.llm.providers.stub import StubLLMProvider
    stub = StubLLMProvider()
    tags = ["<node:plan_action>", "<node:sync_title>", "<node:sync_schema>",
            "<node:sync_entities>", "<node:sync_tools>", "<node:sync_prompts>"]
    for tag in tags:
        out = stub.complete(f"{tag}\nDataset name: d\nTable: t\nTables available: t\nTool: list_t").text
        assert "unrecognized node tag" not in out, f"{tag} not handled by stub"
