"""
Infrastructure — SQLite Database Manager

Manages the SQLite connection and schema initialization.
Designed to be lightweight and zero-dependency.

THREAD-SAFETY:
- WAL mode enabled for concurrent read/write safety
- Write lock serializes all mutations
- check_same_thread=False required because consumer thread and
  async handlers share the connection
"""

from __future__ import annotations

from src.domain.config.constants import DB_BUSY_TIMEOUT_MS

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database connection and schema.

    Uses WAL journal mode for safe concurrent reads alongside writes,
    and a threading lock to serialize write operations.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        # WHY: SQLite with check_same_thread=False allows multi-threaded access
        # but does not guarantee thread-safe writes. This lock serializes all
        # write operations to prevent corruption.
        self._write_lock = threading.Lock()

    def connect(self) -> None:
        """Establish connection to SQLite database."""
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                self._db_path,
                check_same_thread=False,
            )
            self._connection.row_factory = sqlite3.Row

            # Enable WAL mode for concurrent read/write safety
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")

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
            with self._write_lock:
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

    def execute_write(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a write query under the write lock."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        with self._write_lock:
            return self._connection.execute(query, params)

    def commit(self) -> None:
        """Commit transaction under the write lock."""
        if self._connection:
            with self._write_lock:
                self._connection.commit()

    def get_recent_sessions(self, limit: int = 5) -> list[sqlite3.Row]:
        """Get recent sessions ordered by timestamp desc."""
        if not self._connection:
            return []
        
        cursor = self.execute(
            "SELECT * FROM sessions ORDER BY timestamp DESC LIMIT ?", 
            (limit,)
        )
        return cursor.fetchall()

    def delete_sessions_older_than(self, keep_latest: int = 10) -> int:
        """Delete sessions beyond the keep_latest count. Returns deleted count."""
        if not self._connection:
            return 0

        with self._write_lock:
            cursor = self._connection.execute(
                """
                DELETE FROM sessions WHERE id NOT IN (
                    SELECT id FROM sessions ORDER BY id DESC LIMIT ?
                )
                """,
                (keep_latest,)
            )
            deleted = cursor.rowcount
            self._connection.commit()

        if deleted > 0:
            logger.info("Cleaned up %d old sessions (kept latest %d)", deleted, keep_latest)
        return deleted
