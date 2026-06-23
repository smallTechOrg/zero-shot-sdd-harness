from data_analysis_agent.domain.models import DataSource, Session, QueryRecord, AgentRunRecord


def test_datasource_defaults():
    ds = DataSource(name="sales.csv")
    assert ds.id is not None
    assert ds.type == "csv"
    assert ds.column_names == []
    assert ds.row_count is None


def test_session_defaults():
    s = Session(data_source_ids=["ds1", "ds2"])
    assert s.id is not None
    assert s.name is None
    assert s.data_source_ids == ["ds1", "ds2"]


def test_query_record_defaults():
    qr = QueryRecord(session_id="s1", question="What is the total?")
    assert qr.id is not None
    assert qr.status == "pending"
    assert qr.answer is None


def test_agent_run_record_defaults():
    run = AgentRunRecord(query_record_id="xyz")
    assert run.id is not None
    assert run.status == "pending"
