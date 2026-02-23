from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from src.domain.config.constants import DB_BUSY_TIMEOUT_MS

logger = logging.getLogger(__name__)


def build_engine(db_path: Path) -> Engine:
    """Create a SQLite engine with WAL mode, busy timeout, and initialized schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
        cursor.close()

    _init_schema(engine)
    logger.info("SQLAlchemy engine ready: %s", db_path)
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def _init_schema(engine: Engine) -> None:
    """Create all tables and apply column migrations."""
    from src.infrastructure.database.models import Base  # avoid circular at module load

    Base.metadata.create_all(engine)

    # Migration: add source_type column to existing databases that pre-date it.
    with engine.connect() as conn, contextlib.suppress(Exception):
        conn.execute(
            text(
                "ALTER TABLE sessions ADD COLUMN source_type TEXT DEFAULT 'USER_BLOCK'"
            )
        )
        conn.commit()
        logger.info("Migrated sessions table: added source_type column")

    logger.debug("Database schema initialized")
