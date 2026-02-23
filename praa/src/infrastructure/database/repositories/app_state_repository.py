from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.infrastructure.database.models import AppStateRecord


class AppStateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str) -> str | None:
        stmt = select(AppStateRecord.value).where(AppStateRecord.key == key)
        return self._session.execute(stmt).scalar_one_or_none()

    def set(self, key: str, value: str) -> None:
        """Upsert: insert or replace the value for the given key."""
        record = AppStateRecord(key=key, value=value)
        self._session.merge(record)

    def delete(self, key: str) -> None:
        self._session.execute(delete(AppStateRecord).where(AppStateRecord.key == key))

    def reset(self) -> None:
        """Delete all entries in app_state."""
        self._session.execute(delete(AppStateRecord))
