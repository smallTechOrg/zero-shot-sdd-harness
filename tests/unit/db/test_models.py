import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_analysis_agent.db.models import (
    AgentRunRow,
    Base,
    McpPromptRow,
    McpResourceRow,
    McpServerRow,
    McpToolRow,
    QueryRecordRow,
    SessionMcpServerRow,
    SessionRow,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_create_mcp_server(db):
    srv = McpServerRow(name="sales", type="parquet", uri="parquet:///sales")
    db.add(srv)
    db.commit()
    assert srv.id is not None
    assert srv.version == 1


def test_server_json_accessors(db):
    srv = McpServerRow(name="d", type="parquet", uri="parquet:///d")
    srv.physical_tables = [{"table_name": "orders", "column_names": ["id"]}]
    srv.dataset_schema = {"tables": {"orders": {}}, "relationships": []}
    db.add(srv)
    db.commit()
    db.refresh(srv)
    assert srv.physical_tables[0]["table_name"] == "orders"
    assert srv.dataset_schema["tables"]["orders"] == {}


def test_server_name_and_uri_unique(db):
    db.add(McpServerRow(name="a", type="parquet", uri="parquet:///a"))
    db.commit()
    db.add(McpServerRow(name="a", type="parquet", uri="parquet:///b"))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


def test_tool_json_accessors_and_partial_unique(db):
    srv = McpServerRow(name="s", type="parquet", uri="parquet:///s")
    db.add(srv)
    db.flush()
    t = McpToolRow(server_id=srv.id, name="list_orders", description="d", sql_template="SELECT 1")
    t.input_schema = {"type": "object", "properties": {"q": {"type": "string"}}}
    db.add(t)
    db.commit()
    db.refresh(t)
    assert t.input_schema["properties"]["q"]["type"] == "string"

    # A second ACTIVE tool with the same (server_id, name) violates the partial-unique index.
    db.add(McpToolRow(server_id=srv.id, name="list_orders", description="d2", sql_template="SELECT 2"))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


def test_partial_unique_allows_readd_after_soft_delete(db):
    from datetime import datetime, timezone
    srv = McpServerRow(name="s2", type="parquet", uri="parquet:///s2")
    db.add(srv)
    db.flush()
    old = McpToolRow(server_id=srv.id, name="t", description="old", sql_template="SELECT 1")
    db.add(old)
    db.commit()
    old.deleted_at = datetime.now(timezone.utc)  # soft-delete
    db.add(McpToolRow(server_id=srv.id, name="t", description="new", sql_template="SELECT 2"))
    db.commit()  # re-add of a soft-deleted name must NOT collide
    active = db.query(McpToolRow).filter_by(server_id=srv.id, name="t", deleted_at=None).all()
    assert len(active) == 1 and active[0].description == "new"


def test_resource_and_prompt_rows(db):
    srv = McpServerRow(name="s3", type="parquet", uri="parquet:///s3")
    db.add(srv)
    db.flush()
    r = McpResourceRow(server_id=srv.id, uri="dataset://s3/schema", name="schema", kind="schema")
    r.content = {"tables": {}}
    p = McpPromptRow(server_id=srv.id, name="explore")
    db.add_all([r, p])
    db.commit()
    db.refresh(r)
    assert r.content == {"tables": {}}
    assert p.arguments == []


def test_session_servers_and_query_record(db):
    srv = McpServerRow(name="s4", type="parquet", uri="parquet:///s4")
    db.add(srv)
    db.flush()
    sess = SessionRow(name="Test session")
    db.add(sess)
    db.flush()
    db.add(SessionMcpServerRow(session_id=sess.id, mcp_server_id=srv.id))
    qr = QueryRecordRow(session_id=sess.id, question="What is the average?")
    db.add(qr)
    db.flush()
    db.add(AgentRunRow(query_record_id=qr.id))
    db.commit()
    assert qr.status == "pending"
    assert qr.query_history == []
    links = db.query(SessionMcpServerRow).filter_by(session_id=sess.id).all()
    assert len(links) == 1
