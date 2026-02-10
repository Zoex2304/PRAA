"""
Infrastructure — SQLite Database Manager

Manages the SQLite connection and schema initialization.
Designed to be lightweight and zero-dependency.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database connection and schema.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Establish connection to SQLite database."""
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                self._db_path,
                check_same_thread=False,  # Allow multi-threaded access (careful!)
            )
            self._connection.row_factory = sqlite3.Row
            logger.info("Connected to database: %s", self._db_path)
            self._init_schema()
        except sqlite3.Error as e:
            logger.exception("Failed to connect to database: %s", e)
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    def _init_schema(self) -> None:
        """Initialize database schema if not exists."""
        if not self._connection:
            return

        schema = """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            text_content TEXT NOT NULL,
            audio_paths TEXT NOT NULL,   -- JSON list of file paths
            word_boundaries TEXT,        -- JSON list of boundaries
            config_snapshot TEXT         -- JSON snapshot of settings
        );
        """
        try:
            self._connection.executescript(schema)
            self._connection.commit()
            logger.debug("Database schema initialized")
        except sqlite3.Error as e:
            logger.exception("Failed to initialize schema: %s", e)

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return the cursor."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection.execute(query, params)

    def commit(self) -> None:
        """Commit transaction."""
        if self._connection:
            self._connection.commit()
