import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from data_analyst.db.models import Base, SessionRow, MessageRow, DatasetRow


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as session:
        yield session
    engine.dispose()


def test_session_table_name():
    assert SessionRow.__tablename__ == "sessions"


def test_message_table_name():
    assert MessageRow.__tablename__ == "messages"


def test_dataset_table_name():
    assert DatasetRow.__tablename__ == "datasets"


def test_create_session_row(db_session):
    row = SessionRow(title="Test Session")
    db_session.add(row)
    db_session.commit()
    found = db_session.get(SessionRow, row.id)
    assert found is not None
    assert found.title == "Test Session"
    assert found.id is not None
    assert found.created_at is not None


def test_message_fk(db_session):
    session = SessionRow(title="S1")
    db_session.add(session)
    db_session.flush()
    msg = MessageRow(session_id=session.id, role="user", content="hello")
    db_session.add(msg)
    db_session.commit()
    assert msg.id is not None
    assert msg.role == "user"


def test_dataset_defaults(db_session):
    session = SessionRow(title="S2")
    db_session.add(session)
    db_session.flush()
    ds = DatasetRow(
        session_id=session.id,
        original_filename="test.csv",
        table_name="test",
        file_path="/tmp/test.csv",
        file_format="csv",
        row_count=10,
    )
    db_session.add(ds)
    db_session.commit()
    assert ds.id is not None
    assert ds.row_count == 10
    assert ds.registered_at is not None


def test_cascade_delete(db_session):
    session = SessionRow(title="S3")
    db_session.add(session)
    db_session.flush()
    msg = MessageRow(session_id=session.id, role="user", content="q")
    ds = DatasetRow(
        session_id=session.id,
        original_filename="f.csv",
        table_name="f",
        file_path="/tmp/f.csv",
        file_format="csv",
        row_count=0,
    )
    db_session.add_all([msg, ds])
    db_session.commit()
    db_session.delete(session)
    db_session.commit()
    assert db_session.get(MessageRow, msg.id) is None
    assert db_session.get(DatasetRow, ds.id) is None
