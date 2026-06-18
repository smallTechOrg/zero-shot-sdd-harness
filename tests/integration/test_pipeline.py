"""Integration test: stub pipeline runs end-to-end, RunRow status=completed."""
import io
import pytest
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import datachat.db.session as session_module
from datachat.db.models import Base, RunRow, SessionRow
from datachat.graph.runner import run_agent
from datachat.graph.nodes import _dataframe_store


@pytest.fixture(autouse=True)
def _stub_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATACHAT_DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("DATACHAT_GEMINI_API_KEY", "")


@pytest.fixture(autouse=True)
def _use_sqlite(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _reset_llm(monkeypatch):
    import datachat.llm.client as llm_module
    monkeypatch.setattr(llm_module, "_provider", None)
    yield
    monkeypatch.setattr(llm_module, "_provider", None)


def test_pipeline_runs_end_to_end(_use_sqlite, _stub_env):
    df = pd.DataFrame({"city": ["Paris", "London"], "population": [2_161_000, 8_982_000]})

    with session_module.create_db_session() as db:
        sess = SessionRow(filename="cities.csv", status="ready", row_count=2, column_names='["city","population"]')
        db.add(sess)
        db.flush()
        session_id = sess.id

    result = run_agent(session_id, "What is the average population?", df)

    assert result["answer"]
    assert result["llm_provider"] == "stub"

    with Session(session_module._engine) as db:
        run = db.query(RunRow).filter(RunRow.session_id == session_id).first()
        assert run is not None
        assert run.status in ("completed", "force_completed")
