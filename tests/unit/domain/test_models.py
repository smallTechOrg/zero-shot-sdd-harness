from datetime import datetime, timezone

from data_analyst.domain.models import Session, Message, Run, Role, SessionStatus


def _now():
    return datetime.now(timezone.utc)


def test_session_model():
    s = Session(
        id="abc",
        filename="data.csv",
        file_path="/tmp/data.csv",
        file_size_bytes=1024,
        row_count=10,
        column_names=["a", "b"],
        column_dtypes={"a": "int64", "b": "object"},
        status=SessionStatus.ready,
        created_at=_now(),
        last_active_at=_now(),
    )
    assert s.status == SessionStatus.ready
    assert s.error_message is None


def test_message_model():
    m = Message(
        id="msg-1",
        session_id="sess-1",
        role=Role.user,
        content="What is the average age?",
        created_at=_now(),
    )
    assert m.role == Role.user
    assert m.reasoning_trace is None


def test_run_model():
    r = Run(
        id="run-1",
        session_id="sess-1",
        created_at=_now(),
    )
    assert r.status == "running"
    assert r.action_history == []
