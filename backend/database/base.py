"""
SQLAlchemy 2.x declarative base and mixins.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def generate_uuid_str() -> str:
    """Generate string UUIDv4."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base class for all persistence models."""
    pass


class TimestampMixin:
    """Standard timestamp audit columns."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
