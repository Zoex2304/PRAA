"""
Domain — Database Manager Service

Provides cache clearing and full data flush operations.
Used exclusively by the Database Management page.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from src.infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


class DbManagerService:
    """Service for destructive DB/cache operations with stat reporting."""

    def __init__(self, db_manager: DatabaseManager, cache_dir: Path) -> None:
        self._db = db_manager
        self._cache_dir = cache_dir

    def get_stats(self) -> Dict[str, object]:
        """Return current stats: session_count and cache_size_mb."""
        return {
            "session_count": self._db.get_sessions_count(),
            "cache_size_mb": self._get_cache_size_mb(),
        }

    def clear_cache(self) -> int:
        """Delete all audio cache files. Returns number of files deleted."""
        count = self._delete_cache_files()
        logger.info("Cleared audio cache: %d files deleted", count)
        return count

    def flush_all(self) -> Dict[str, int]:
        """Delete all sessions from DB and all cache files."""
        sessions = self._db.delete_all_sessions()
        files = self._delete_cache_files()
        logger.info("Flushed all data: %d sessions, %d cache files", sessions, files)
        return {"sessions": sessions, "files": files}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _delete_cache_files(self) -> int:
        count = 0
        if self._cache_dir.exists():
            for f in self._cache_dir.iterdir():
                if f.is_file():
                    try:
                        f.unlink()
                        count += 1
                    except Exception:
                        logger.debug("Could not delete cache file: %s", f)
        return count

    def _get_cache_size_mb(self) -> float:
        total = 0
        if self._cache_dir.exists():
            for f in self._cache_dir.iterdir():
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except Exception:
                        pass
        return round(total / (1024 * 1024), 2)
