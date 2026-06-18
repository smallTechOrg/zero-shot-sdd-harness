import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from data_analyst.db.models import Base, SessionRow, MessageRow, RunRow


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as session:
        yield session
    engine.dispose()


def test_create_session_row(db_session):
    row = SessionRow(
        filename="test.csv",
        file_path="/tmp/test.csv",
        file_size_bytes=512,
        row_count=5,
        column_names=json.dumps(["x", "y"]),
        column_dtypes=json.dumps({"x": "int64", "y": "float64"}),
    )
    db_session.add(row)
    db_session.commit()
    assert row.id is not None
    assert row.get_column_names() == ["x", "y"]
    assert row.get_column_dtypes() == {"x": "int64", "y": "float64"}


def test_message_cascade_delete(db_session):
    session_row = SessionRow(
        filename="data.csv",
        file_path="/tmp/data.csv",
        file_size_bytes=100,
        row_count=1,
        column_names="[]",
        column_dtypes="{}",
    )
    db_session.add(session_row)
    db_session.flush()

    msg = MessageRow(
        session_id=session_row.id,
        role="user",
        content="Hello",
    )
    db_session.add(msg)
    db_session.commit()

    db_session.delete(session_row)
    db_session.commit()
    assert db_session.get(MessageRow, msg.id) is None


def test_run_row(db_session):
    session_row = SessionRow(
        filename="run_test.csv",
        file_path="/tmp/run_test.csv",
        file_size_bytes=200,
        row_count=3,
        column_names="[]",
        column_dtypes="{}",
    )
    db_session.add(session_row)
    db_session.flush()

    run = RunRow(session_id=session_row.id)
    db_session.add(run)
    db_session.commit()
    assert run.status == "running"
    assert run.get_action_history() == []
