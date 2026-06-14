import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from datachat.db.models import Base, UploadRow, QueryRow


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as session:
        yield session
    engine.dispose()


def test_upload_row_create_and_read(db_session):
    row = UploadRow(
        filename="abc123.csv",
        original_filename="data.csv",
        row_count=100,
        columns_json=json.dumps(["name", "age", "city"]),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    assert row.id is not None
    assert row.original_filename == "data.csv"
    assert row.row_count == 100
    assert row.columns == ["name", "age", "city"]
    assert row.uploaded_at is not None


def test_query_row_create_and_read(db_session):
    upload = UploadRow(
        filename="abc.csv",
        original_filename="test.csv",
        row_count=5,
        columns_json=json.dumps(["col1"]),
    )
    db_session.add(upload)
    db_session.flush()

    qrow = QueryRow(
        upload_id=upload.id,
        question="What is the average age?",
        answer="The average age is 30.",
    )
    db_session.add(qrow)
    db_session.commit()
    db_session.refresh(qrow)

    assert qrow.id is not None
    assert qrow.upload_id == upload.id
    assert qrow.answer == "The average age is 30."
    assert qrow.created_at is not None


def test_tables_created(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/schema_test.db")
    Base.metadata.create_all(engine)
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "uploads" in tables
    assert "queries" in tables
    engine.dispose()
