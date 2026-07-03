"""Phase-2 conversation-memory + live-progress guarantees.

These test the *code-level* guarantees behind the capability specs, without
needing a live Gemini call:

  * conversation_sessions.md #3 — memory is capped at ``MAX_HISTORY_TURNS`` (6):
    an N+1-turn session threads only the last 6 turns into the prompt.
  * conversation_sessions.md #4 — no cross-dataset leak: a turn in a session on
    dataset X never surfaces when loading a session on dataset Y.
  * cost_and_progress.md:35 — the runner's node->step mapping emits, in order,
    planning -> running code -> writing answer, and surfaces "Retrying…" on a
    retry loop.

They use the isolated production-driver DB fixture from ``tests/conftest.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.models import DatasetRow, SessionRow, RunRow
from db.session import create_db_session


def _make_dataset(session, name: str = "ds") -> str:
    ds = DatasetRow(
        name=name,
        original_filename=f"{name}.csv",
        file_path=f"/tmp/{name}.csv",
        file_format="csv",
        size_bytes=1,
        row_count=1,
        column_count=1,
        profile_json="{}",
    )
    session.add(ds)
    session.flush()
    return ds.id


def _make_session(session, dataset_id: str) -> str:
    s = SessionRow(dataset_id=dataset_id)
    session.add(s)
    session.flush()
    return s.id


def _add_completed_run(
    session, *, dataset_id: str, session_id: str, question: str, answer: str, created_at
) -> str:
    run = RunRow(
        dataset_id=dataset_id,
        session_id=session_id,
        question=question,
        answer_text=answer,
        status="completed",
        created_at=created_at,
    )
    session.add(run)
    session.flush()
    return run.id


# --------------------------------------------------------------------------- #
# conversation_sessions.md #3 — memory cap MAX_HISTORY_TURNS = 6
# --------------------------------------------------------------------------- #
def test_memory_capped_to_max_history_turns():
    from graph.runner import MAX_HISTORY_TURNS, _load_session_messages

    assert MAX_HISTORY_TURNS == 6

    base = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
    n_turns = MAX_HISTORY_TURNS + 3  # 9 turns — three over the cap.

    with create_db_session() as session:
        dataset_id = _make_dataset(session, "capds")
        session_id = _make_session(session, dataset_id)
        for i in range(n_turns):
            _add_completed_run(
                session,
                dataset_id=dataset_id,
                session_id=session_id,
                question=f"Q{i}",
                answer=f"A{i}",
                created_at=base + timedelta(minutes=i),
            )

    messages = _load_session_messages(session_id)

    # Only the LAST 6 turns are threaded into the prompt, oldest -> newest.
    assert len(messages) == MAX_HISTORY_TURNS
    assert [m["question"] for m in messages] == [f"Q{i}" for i in range(3, n_turns)]
    assert [m["answer"] for m in messages] == [f"A{i}" for i in range(3, n_turns)]
    # The three oldest turns are dropped, never sent.
    assert "Q0" not in [m["question"] for m in messages]


# --------------------------------------------------------------------------- #
# conversation_sessions.md #4 — no cross-dataset turn leak
# --------------------------------------------------------------------------- #
def test_no_cross_dataset_turn_leak():
    from graph.runner import _load_session_messages

    base = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)

    with create_db_session() as session:
        dataset_x = _make_dataset(session, "X")
        dataset_y = _make_dataset(session, "Y")
        session_a = _make_session(session, dataset_x)
        session_b = _make_session(session, dataset_y)

        _add_completed_run(
            session,
            dataset_id=dataset_x,
            session_id=session_a,
            question="SECRET_X_QUESTION",
            answer="SECRET_X_ANSWER",
            created_at=base,
        )
        _add_completed_run(
            session,
            dataset_id=dataset_y,
            session_id=session_b,
            question="Y_QUESTION",
            answer="Y_ANSWER",
            created_at=base + timedelta(minutes=1),
        )

    b_messages = _load_session_messages(session_b)

    # Session B (dataset Y) must see ONLY its own turn — never dataset X's.
    assert [m["question"] for m in b_messages] == ["Y_QUESTION"]
    leaked = "SECRET_X" in "".join(
        f"{m['question']}{m['answer']}" for m in b_messages
    )
    assert not leaked, f"dataset X's turn leaked into session B: {b_messages}"


# --------------------------------------------------------------------------- #
# cost_and_progress.md:35 — SSE step sequence planning -> running -> writing
# plus the "Retrying…" path
# --------------------------------------------------------------------------- #
class _CapturingBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, str]] = []

    def publish(self, run_id: str, step: str, detail: str = "") -> None:
        self.events.append((run_id, step, detail))

    def finish(self, run_id: str, status: str = "completed") -> None:
        self.events.append((run_id, "done", status))


def test_progress_step_sequence_maps_nodes_in_order(monkeypatch):
    import graph.runner as runner

    bus = _CapturingBus()
    monkeypatch.setattr(runner, "progress_bus", bus)

    run_id = "run-seq"
    # Simulate the graph streaming node-by-node in execution order (happy path).
    runner._publish_progress(run_id, "load_context", {})
    runner._publish_progress(run_id, "generate_code", {"attempts": 1})
    runner._publish_progress(run_id, "execute_code", {})
    runner._publish_progress(run_id, "write_answer", {})

    steps = [step for (_rid, step, _detail) in bus.events]

    # The spec's required ordering: planning/generating -> running code ->
    # writing answer. load_context + first generate_code both surface as
    # "Planning…"; the important thing is the relative order.
    assert steps == ["Planning…", "Planning…", "Running code…", "Writing answer…"]
    # Running code must precede writing the answer.
    assert steps.index("Running code…") < steps.index("Writing answer…")


def test_progress_step_shows_retrying_on_retry_loop(monkeypatch):
    import graph.runner as runner

    bus = _CapturingBus()
    monkeypatch.setattr(runner, "progress_bus", bus)

    run_id = "run-retry"
    # A second generate_code entry (attempts > 1) is the bounded retry loop.
    runner._publish_progress(run_id, "generate_code", {"attempts": 1})
    runner._publish_progress(run_id, "execute_code", {})
    runner._publish_progress(run_id, "generate_code", {"attempts": 2})

    steps = [step for (_rid, step, _detail) in bus.events]
    assert steps == ["Planning…", "Running code…", "Retrying…"]
    assert "Retrying…" in steps
