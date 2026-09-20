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



from urllib.parse import urlparse


def get_database_url() -> str:
    """Retrieve database URL from environment or default to local sqlite/postgres."""
    url = os.getenv("DATABASE_URL", "sqlite:///./vfx_platform.db").strip()
    # Render/Heroku legacy dialect prefix normalization for SQLAlchemy 2.0
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Detect if running in cloud container (Render/Docker) with an invalid localhost host
    is_cloud = bool(os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"))
    if url.startswith("postgresql://"):
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            if is_cloud and (not host or host in ("localhost", "127.0.0.1", "::1")):
                print("\n" + "=" * 75)
                print(" [CONFIG WARNING] DATABASE_URL points to 'localhost' inside Render!")
                print(" PostgreSQL does not run inside the web service container.")
                print(" In your Render Web Service -> Environment:")
                print(" Set DATABASE_URL to your Render PostgreSQL Internal or External URL.")
                print(" (e.g. postgresql://user:pass@dpg-xxxx.oregon-postgres.render.com/dbname)")
                print(" Temporarily falling back to SQLite to allow server to boot.")
                print("=" * 75 + "\n")
                return "sqlite:///./vfx_platform.db"
        except Exception:
            pass

    # Ensure SSL for external Render and cloud database connections
    if ("render.com" in url or "supabase" in url or "neon.tech" in url) and "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


# Default sync engine and session factory with automatic fallback
def create_default_engine():
    """Create a database engine with fallback to SQLite if PostgreSQL is unreachable."""
    url = get_database_url()
    echo = os.getenv("SQL_ECHO", "false").lower() == "true"

    if url.startswith("postgresql://") or url.startswith("postgres://"):
        try:
            probe_engine = create_engine(
                url,
                echo=False,
                connect_args={"connect_timeout": 3},
                pool_pre_ping=True,
            )
            with probe_engine.connect() as conn:
                pass
            return probe_engine
        except Exception as exc:
            masked = url.split("@")[-1] if "@" in url else "postgresql"
            print(f"\n[DATABASE NOTICE] PostgreSQL connection to '{masked}' failed ({exc}).")
            print("[DATABASE NOTICE] Gracefully falling back to SQLite engine (vfx_platform.db).\n")
            url = "sqlite:///./vfx_platform.db"

    c_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=echo, connect_args=c_args, pool_pre_ping=True)


engine = create_default_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine=None) -> None:
    """Initialize all database tables defined on Base.metadata."""
    eng = target_engine or engine
    try:
        Base.metadata.create_all(bind=eng)
    except Exception as exc:
        print(f"[DATABASE NOTICE] init_db error: {exc}")


# Auto-initialize database tables immediately when engine is created
try:
    init_db(engine)
except Exception as _auto_init_err:
    print(f"[DATABASE NOTICE] Auto-initialization warning: {_auto_init_err}")


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
