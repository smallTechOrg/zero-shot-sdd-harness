import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from analyst.db.models import SessionRow
from analyst.domain.session import Session


def create_session(db: DBSession) -> Session:
    """Create a new session in the database."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    session = Session(session_id=session_id, created_at=now, last_active_at=now)
    row = SessionRow(
        session_id=session_id,
        created_at=now,
        last_active_at=now,
        state_json=session.model_dump_json(),
    )
    db.add(row)
    db.commit()
    return session


def get_session(session_id: str, db: DBSession) -> Session | None:
    """Return Session or None if not found."""
    row = db.get(SessionRow, session_id)
    if row is None:
        return None
    return Session.model_validate_json(row.state_json)


def update_session(session: Session, db: DBSession) -> None:
    """Persist updated session state."""
    row = db.get(SessionRow, session.session_id)
    if row is None:
        raise ValueError(f"Session {session.session_id} not found")
    row.state_json = session.model_dump_json()
    row.last_active_at = datetime.now(timezone.utc)
    db.commit()
