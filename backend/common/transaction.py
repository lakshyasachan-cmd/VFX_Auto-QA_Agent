"""
Database Transaction Boundaries and Unit of Work Helpers.
Guarantees clean commit / rollback boundaries and ensures atomic mutations
across incidents, agent runs, reasoning, remediation plans, approvals, and audit logs.
"""

from contextlib import contextmanager
import logging
from typing import Generator, Optional
from sqlalchemy.orm import Session

from backend.database.session import SessionLocal

logger = logging.getLogger("vfx.common.transaction")


@contextmanager
def db_transaction(session: Optional[Session] = None) -> Generator[Session, None, None]:
    """
    Context manager providing strict database transaction boundaries.
    Commits on successful block completion, rolls back cleanly on unhandled exceptions.
    If an existing session is passed, participates in that session without auto-closing it.
    """
    is_nested = session is not None
    active_session = session or SessionLocal()

    try:
        yield active_session
        active_session.commit()
    except Exception as exc:
        active_session.rollback()
        logger.error("Transaction rolled back due to error: %s", exc, exc_info=True)
        raise
    finally:
        if not is_nested:
            active_session.close()
