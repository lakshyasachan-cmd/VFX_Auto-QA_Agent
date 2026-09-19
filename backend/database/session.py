"""
Database engine and session management.
Supports PostgreSQL (production) and SQLite (tests and local development).
"""

import os
from collections.abc import Generator
from typing import Any
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure .env is loaded before reading DATABASE_URL
load_dotenv(override=True)


from backend.database.base import Base
# Ensure all models are imported so Base.metadata knows about them
import backend.database.models  # noqa: F401



def get_database_url() -> str:
    """Retrieve database URL from environment or default to local sqlite/postgres."""
    return os.getenv("DATABASE_URL", "sqlite:///./vfx_platform.db")


# Default sync engine and session factory
_default_url = get_database_url()
connect_args = {"check_same_thread": False} if _default_url.startswith("sqlite") else {}

engine = create_engine(
    _default_url,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine=None) -> None:
    """Initialize all database tables defined on Base.metadata."""
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)


def drop_db(target_engine=None) -> None:
    """Drop all tables (used primarily in test teardown)."""
    eng = target_engine or engine
    Base.metadata.drop_all(bind=eng)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_custom_session(db_url: str) -> tuple[Any, sessionmaker]:
    """Create isolated engine and sessionmaker for tests or custom connection strings."""
    c_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    custom_engine = create_engine(db_url, connect_args=c_args, pool_pre_ping=True)
    custom_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=custom_engine)
    return custom_engine, custom_session_factory
