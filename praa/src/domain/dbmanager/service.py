"""
Domain — Database Manager Service

Provides cache clearing and full data flush operations.
Used exclusively by the Database Management page.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from src.infrastructure.database.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class DbManagerService:
    """Service for destructive DB/cache operations with stat reporting."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        cache_dir: Path,
        ocr_debug_dir: Path | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._cache_dir = cache_dir
        self._ocr_debug_dir = ocr_debug_dir

    def get_stats(self) -> dict[str, object]:
        """Return current stats: session_count and cache_size_mb."""
        with self._uow_factory() as uow:
            count = uow.sessions.count()
        return {
            "session_count": count,
            "cache_size_mb": self._get_cache_size_mb(),
        }

    def clear_cache(self) -> int:
        """Delete all audio cache files. Returns number of files deleted."""
        count = self._delete_cache_files()
        logger.info("Cleared audio cache: %d files deleted", count)
        return count

    def flush_all(self) -> dict[str, int]:
        """Delete all sessions, cache files, and OCR debug screenshots. Resets app state."""
        with self._uow_factory() as uow:
            sessions = uow.sessions.delete_all()
            uow.app_state.reset()
            uow.commit()
        files = self._delete_cache_files()
        ocr_files = self._delete_ocr_debug_files()
        logger.info(
            "Flushed all data: %d sessions, %d cache files, %d ocr debug files",
            sessions,
            files,
            ocr_files,
        )
        return {"sessions": sessions, "files": files, "ocr_files": ocr_files}

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

    def _delete_ocr_debug_files(self) -> int:
        """Recursively delete all contents of the OCR debug directory."""
        if not self._ocr_debug_dir or not self._ocr_debug_dir.exists():
            return 0
        count = 0
        for item in self._ocr_debug_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    count += 1
                elif item.is_dir():
                    count += sum(1 for _ in item.rglob("*") if _.is_file())
                    shutil.rmtree(item)
            except Exception:
                logger.debug("Could not delete OCR debug item: %s", item)
        return count

    def _get_cache_size_mb(self) -> float:
        total = 0
        if self._cache_dir.exists():
            for f in self._cache_dir.iterdir():
                if f.is_file():
                    with contextlib.suppress(Exception):
                        total += f.stat().st_size
        return round(total / (1024 * 1024), 2)
