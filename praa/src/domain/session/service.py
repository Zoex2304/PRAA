"""
Domain — Session Service (Persistent History)

Manages active session state and persistence to SQLite.
Acts as the "Store" (Zustand-like) for the application's history.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

from src.infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Represents a TTS session (text + audio + metadata)."""
    id: int
    timestamp: str  # ISO8601
    text_content: str
    audio_paths: List[str]  # List of absolute paths
    word_boundaries: Dict[str, Any]  # JSON dict
    config_snapshot: Dict[str, Any]


class SessionService:
    """
    Session Manager acting as the single source of truth for history.
    
    Persists sessions to SQLite and manages audio file caching.
    """

    def __init__(self, db_manager: DatabaseManager, cache_dir: Path) -> None:
        self._db = db_manager
        self._cache_dir = cache_dir
        self._current_session: Optional[Session] = None
        
        # Ensure cache directory exists
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def save_session(
        self,
        text: str,
        audio_paths: List[Path],
        word_boundaries: Dict[int, List[tuple]],
        config: Dict[str, Any],
    ) -> Session:
        """
        Save a new session to DB and persist audio files to cache.
        """
        try:
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            
            # 1. Copy audio files to permanent cache
            cached_paths = []
            for path in audio_paths:
                if path.exists():
                    dest = self._cache_dir / f"{timestamp.replace(':', '-')}_{path.name}"
                    shutil.copy2(path, dest)
                    cached_paths.append(str(dest))
            
            if not cached_paths:
                logger.warning("No audio files to save for session")
                
            # 2. Serialize metadata
            audio_json = json.dumps(cached_paths)
            boundaries_json = json.dumps(word_boundaries)
            config_json = json.dumps(config)
            
            # 3. Insert into DB
            cursor = self._db.execute_write(
                """
                INSERT INTO sessions (timestamp, text_content, audio_paths, word_boundaries, config_snapshot)
                VALUES (?, ?, ?, ?, ?)
                """,
                (timestamp, text, audio_json, boundaries_json, config_json)
            )
            self._db.commit()
            
            # 4. Update current session state
            session_id = cursor.lastrowid
            self._current_session = Session(
                id=session_id,
                timestamp=timestamp,
                text_content=text,
                audio_paths=cached_paths,
                word_boundaries=word_boundaries,
                config_snapshot=config,
            )
            
            logger.info("Session saved: ID=%d, AudioFiles=%d", session_id, len(cached_paths))
            return self._current_session
            
        except Exception:
            logger.exception("Failed to save session")
            raise

    def get_last_session(self) -> Optional[Session]:
        """Retrieve the most recent session from DB."""
        try:
            cursor = self._db.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            
            if row:
                return Session(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    text_content=row["text_content"],
                    audio_paths=json.loads(row["audio_paths"]),
                    word_boundaries=json.loads(row["word_boundaries"]) if row["word_boundaries"] else {},
                    config_snapshot=json.loads(row["config_snapshot"]) if row["config_snapshot"] else {},
                )
            return None
            
        except Exception:
            logger.exception("Failed to retrieve last session")
            return None

    def get_recent_sessions(self, limit: int = 5) -> List[Session]:
        """Get list of recent sessions."""
        try:
            rows = self._db.get_recent_sessions(limit)
            sessions = []
            for row in rows:
                sessions.append(Session(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    text_content=row["text_content"],
                    audio_paths=json.loads(row["audio_paths"]),
                    word_boundaries=json.loads(row["word_boundaries"]) if row["word_boundaries"] else {},
                    config_snapshot=json.loads(row["config_snapshot"]) if row["config_snapshot"] else {},
                ))
            return sessions
        except Exception:
            logger.exception("Failed to retrieve recent sessions")
            return []

    def get_text_slice(self, text: str, start_word_idx: int) -> str:
        """
        Smart Resume Helper: Returns text starting from word index.
        (Used for real-time speed/voice change resume).
        """
        # Simple implementation: split by space. 
        # For more robustness, use robust word boundary indices if available.
        words = text.split()
        if start_word_idx >= len(words):
            return ""
        return " ".join(words[start_word_idx:])

    def cleanup_old_sessions(self, max_items: int = 10) -> None:
        """Keep only the last N sessions and delete old audio cache files."""
        try:
            # Get sessions that will be deleted
            all_sessions = self._db.execute(
                "SELECT audio_paths FROM sessions ORDER BY id DESC"
            ).fetchall()

            # Sessions beyond the limit will be deleted
            for row in all_sessions[max_items:]:
                try:
                    paths = json.loads(row["audio_paths"])
                    for p in paths:
                        path = Path(p)
                        if path.exists():
                            path.unlink()
                except Exception:
                    pass  # Best-effort cleanup

            # Delete old DB records
            deleted = self._db.delete_sessions_older_than(max_items)
            if deleted > 0:
                logger.info("Cleaned up %d old sessions and their audio files", deleted)

        except Exception:
            logger.exception("Failed to cleanup old sessions")
