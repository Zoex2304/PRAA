from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.infrastructure.database.models import SessionRecord

logger = logging.getLogger(__name__)


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: SessionRecord) -> SessionRecord:
        """Persist a new record and flush to populate its auto-generated ID."""
        self._session.add(record)
        self._session.flush()
        return record

    def get_latest(self) -> SessionRecord | None:
        stmt = select(SessionRecord).order_by(SessionRecord.id.desc()).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()

    def get_recent(self, limit: int = 5) -> Sequence[SessionRecord]:
        stmt = (
            select(SessionRecord).order_by(SessionRecord.timestamp.desc()).limit(limit)
        )
        return self._session.execute(stmt).scalars().all()

    def count(self) -> int:
        stmt = select(func.count()).select_from(SessionRecord)
        return self._session.execute(stmt).scalar_one()

    def delete_all(self) -> int:
        result = self._session.execute(delete(SessionRecord))
        return result.rowcount

    def delete_older_than(self, keep_latest: int = 10) -> int:
        keep_ids = self._get_latest_ids(keep_latest)
        if not keep_ids:
            result = self._session.execute(delete(SessionRecord))
            return result.rowcount
        result = self._session.execute(
            delete(SessionRecord).where(SessionRecord.id.notin_(keep_ids))
        )
        return result.rowcount

    def get_audio_paths_for_older_than(self, keep_latest: int = 10) -> list[str]:
        """Return audio_paths JSON strings for sessions that will be pruned."""
        keep_ids = self._get_latest_ids(keep_latest)
        stmt = select(SessionRecord.audio_paths).where(
            SessionRecord.id.notin_(keep_ids)
        )
        return [row[0] for row in self._session.execute(stmt).all()]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_latest_ids(self, limit: int) -> list[int]:
        stmt = select(SessionRecord.id).order_by(SessionRecord.id.desc()).limit(limit)
        return [row[0] for row in self._session.execute(stmt).all()]
