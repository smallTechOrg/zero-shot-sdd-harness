import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from data_analysis_agent.db.models import (
    Base, DataSourceRow, DatasetTableRow,
    SessionRow, SessionDataSourceRow, QueryRecordRow, AgentRunRow,
)


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_create_datasource(db):
    ds = DataSourceRow(name="sales.csv", type="csv")
    db.add(ds)
    db.commit()
    assert ds.id is not None
    assert ds.name == "sales.csv"


def test_datasource_column_names(db):
    ds = DataSourceRow(name="data.csv", type="csv")
    ds.column_names = ["a", "b", "c"]
    db.add(ds)
    db.commit()
    db.refresh(ds)
    assert ds.column_names == ["a", "b", "c"]


def test_datasource_description_columns(db):
    ds = DataSourceRow(
        name="data.csv",
        type="csv",
        tool_description="A dataset about X.",
        capability_description="Run SQL SELECT against table data.",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    assert ds.tool_description == "A dataset about X."
    assert ds.capability_description == "Run SQL SELECT against table data."


def test_dataset_uri_default_derives_when_unset(db):
    ds = DataSourceRow(name="Q2 Sales", type="parquet")
    db.add(ds)
    db.commit()
    db.refresh(ds)
    assert ds.dataset_uri == "parquet:///Q2%20Sales"  # name URL-encoded, no creds/host
    ds.uri = "postgresql://u:p@h:5432/db"
    assert ds.dataset_uri == "postgresql://u:p@h:5432/db"  # explicit uri wins


def test_dataset_tables_child_and_json_accessors(db):
    ds = DataSourceRow(name="sales_db", type="parquet")
    db.add(ds)
    db.flush()

    t1 = DatasetTableRow(dataset_id=ds.id, table_name="orders", parquet_path="/x/orders.parquet", row_count=3)
    t1.column_names = ["id", "total"]
    t1.schema_json = '[{"name":"id","dtype":"int64","nullable":false}]'
    t2 = DatasetTableRow(dataset_id=ds.id, table_name="customers", parquet_path="/x/customers.parquet")
    db.add_all([t1, t2])
    db.commit()

    tables = db.query(DatasetTableRow).filter_by(dataset_id=ds.id).order_by(DatasetTableRow.table_name).all()
    assert [t.table_name for t in tables] == ["customers", "orders"]
    orders = tables[1]
    assert orders.column_names == ["id", "total"]
    assert orders.schema[0]["name"] == "id"


def test_dataset_table_unique_constraint(db):
    ds = DataSourceRow(name="d", type="parquet")
    db.add(ds)
    db.flush()
    db.add(DatasetTableRow(dataset_id=ds.id, table_name="t"))
    db.commit()
    db.add(DatasetTableRow(dataset_id=ds.id, table_name="t"))  # duplicate (dataset_id, table_name)
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


def test_create_session_and_query_record(db):
    ds = DataSourceRow(name="data.csv", type="csv")
    db.add(ds)
    db.flush()

    sess = SessionRow(name="Test session")
    db.add(sess)
    db.flush()

    db.add(SessionDataSourceRow(session_id=sess.id, data_source_id=ds.id))
    db.flush()

    qr = QueryRecordRow(session_id=sess.id, question="What is the average?")
    db.add(qr)
    db.commit()
    assert qr.id is not None
    assert qr.status == "pending"


def test_session_many_datasources(db):
    ds1 = DataSourceRow(name="sales.csv", type="csv")
    ds2 = DataSourceRow(name="customers.csv", type="csv")
    db.add_all([ds1, ds2])
    db.flush()

    sess = SessionRow(name="Multi-source session")
    db.add(sess)
    db.flush()

    db.add(SessionDataSourceRow(session_id=sess.id, data_source_id=ds1.id))
    db.add(SessionDataSourceRow(session_id=sess.id, data_source_id=ds2.id))
    db.commit()

    links = db.query(SessionDataSourceRow).filter_by(session_id=sess.id).all()
    assert len(links) == 2


def test_create_agent_run(db):
    ds = DataSourceRow(name="data.csv", type="csv")
    db.add(ds)
    db.flush()
    sess = SessionRow()
    db.add(sess)
    db.flush()
    db.add(SessionDataSourceRow(session_id=sess.id, data_source_id=ds.id))
    db.flush()
    qr = QueryRecordRow(session_id=sess.id, question="Q")
    db.add(qr)
    db.flush()
    run = AgentRunRow(query_record_id=qr.id)
    db.add(run)
    db.commit()
    assert run.id is not None
    assert run.status == "pending"
