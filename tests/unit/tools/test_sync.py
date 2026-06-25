"""Unit tests for the 5-stage sync pipeline (stub mode): generation of tools/resources/prompts,
version bump, soft-delete of dropped capabilities, and stub coverage of every stage tag."""
import datetime as _dt

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_analysis_agent.db.models import Base, McpPromptRow, McpResourceRow, McpServerRow, McpToolRow
from data_analysis_agent.tools.sync import apply_sync_result, run_sync


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


def test_stub_handles_all_node_tags():
    from data_analysis_agent.llm.providers.stub import StubLLMProvider
    stub = StubLLMProvider()
    tags = ["<node:plan_action>", "<node:sync_title>", "<node:sync_schema>",
            "<node:sync_entities>", "<node:sync_tools>", "<node:sync_prompts>"]
    for tag in tags:
        out = stub.complete(f"{tag}\nDataset name: d\nTable: t\nTables available: t\nTool: list_t").text
        assert "unrecognized node tag" not in out, f"{tag} not handled by stub"
