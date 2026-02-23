"""
Domain — Session Service (Persistent History)

Manages active session state and persistence to SQLite via Unit of Work.
Acts as the "Store" (Zustand-like) for the application's history.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.infrastructure.database.models import SessionRecord
from src.infrastructure.database.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Represents a TTS session (text + audio + metadata)."""

    id: int
    timestamp: str  # ISO8601
    text_content: str
    audio_paths: list[str]  # List of absolute paths
    word_boundaries: dict[str, Any]  # JSON dict
    config_snapshot: dict[str, Any]
    source_type: str = "USER_BLOCK"  # Origin: USER_BLOCK | OCR | FILE_UPLOAD


class SessionService:
    """
    Session Manager acting as the single source of truth for history.

    Persists sessions to SQLite via UnitOfWork and manages audio file caching.
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork], cache_dir: Path) -> None:
        self._uow_factory = uow_factory
        self._cache_dir = cache_dir
        self._current_session: Session | None = None

        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def save_session(
        self,
        text: str,
        audio_paths: list[Path],
        word_boundaries: dict[int, list[tuple]],
        config: dict[str, Any],
        source_type: str = "USER_BLOCK",
    ) -> Session:
        """Save a new session to DB and persist audio files to cache."""
        try:
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

            # 1. Copy audio files to permanent cache
            cached_paths: list[str] = []
            for path in audio_paths:
                if path.exists():
                    dest = (
                        self._cache_dir / f"{timestamp.replace(':', '-')}_{path.name}"
                    )
                    shutil.copy2(path, dest)
                    cached_paths.append(str(dest))

            if not cached_paths:
                logger.warning("No audio files to save for session")

            # 2. Build and persist the ORM record
            record = SessionRecord(
                timestamp=timestamp,
                text_content=text,
                audio_paths=json.dumps(cached_paths),
                word_boundaries=json.dumps(word_boundaries),
                config_snapshot=json.dumps(config),
                source_type=source_type,
            )
            with self._uow_factory() as uow:
                uow.sessions.create(record)
                uow.commit()

            # 3. Update in-memory current session
            self._current_session = Session(
                id=record.id,
                timestamp=timestamp,
                text_content=text,
                audio_paths=cached_paths,
                word_boundaries=word_boundaries,
                config_snapshot=config,
                source_type=source_type,
            )

            logger.info(
                "Session saved: ID=%d, AudioFiles=%d", record.id, len(cached_paths)
            )
            return self._current_session

        except Exception:
            logger.exception("Failed to save session")
            raise

    def get_last_session(self) -> Session | None:
        """Retrieve the most recent session from DB."""
        try:
            with self._uow_factory() as uow:
                record = uow.sessions.get_latest()
            if record:
                return Session(
                    id=record.id,
                    timestamp=record.timestamp,
                    text_content=record.text_content,
                    audio_paths=json.loads(record.audio_paths),
                    word_boundaries=json.loads(record.word_boundaries)
                    if record.word_boundaries
                    else {},
                    config_snapshot=json.loads(record.config_snapshot)
                    if record.config_snapshot
                    else {},
                    source_type=record.source_type or "USER_BLOCK",
                )
            return None
        except Exception:
            logger.exception("Failed to retrieve last session")
            return None

    def get_recent_sessions(self, limit: int = 5) -> list[Session]:
        """Get list of recent sessions."""
        try:
            with self._uow_factory() as uow:
                records = uow.sessions.get_recent(limit)
            sessions = []
            for record in records:
                sessions.append(
                    Session(
                        id=record.id,
                        timestamp=record.timestamp,
                        text_content=record.text_content,
                        audio_paths=json.loads(record.audio_paths),
                        word_boundaries=json.loads(record.word_boundaries)
                        if record.word_boundaries
                        else {},
                        config_snapshot=json.loads(record.config_snapshot)
                        if record.config_snapshot
                        else {},
                        source_type=record.source_type or "USER_BLOCK",
                    )
                )
            return sessions
        except Exception:
            logger.exception("Failed to retrieve recent sessions")
            return []

    def get_text_slice(self, text: str, start_word_idx: int) -> str:
        """Smart Resume Helper: Returns text starting from word index."""
        words = text.split()
        if start_word_idx >= len(words):
            return ""
        return " ".join(words[start_word_idx:])

    def cleanup_old_sessions(self, max_items: int = 10) -> None:
        """Keep only the last N sessions and delete old audio cache files."""
        try:
            with self._uow_factory() as uow:
                audio_paths_json_list = uow.sessions.get_audio_paths_for_older_than(
                    max_items
                )
                for audio_json in audio_paths_json_list:
                    try:
                        for p in json.loads(audio_json):
                            path = Path(p)
                            if path.exists():
                                path.unlink()
                    except Exception:
                        pass  # best-effort file cleanup
                deleted = uow.sessions.delete_older_than(max_items)
                uow.commit()

            if deleted > 0:
                logger.info("Cleaned up %d old sessions and their audio files", deleted)

        except Exception:
            logger.exception("Failed to cleanup old sessions")
