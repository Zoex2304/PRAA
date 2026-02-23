from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from src.infrastructure.database.repositories.app_state_repository import (
    AppStateRepository,
)
from src.infrastructure.database.repositories.session_repository import (
    SessionRepository,
)


class UnitOfWork:
    """Context manager that owns a single SQLAlchemy session lifecycle.

    Usage::

        with uow_factory() as uow:
            record = uow.sessions.get_latest()
            uow.commit()
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    # ------------------------------------------------------------------
    # Repository accessors
    # ------------------------------------------------------------------

    @property
    def sessions(self) -> SessionRepository:
        assert self._session is not None, "UnitOfWork must be used as a context manager"
        return SessionRepository(self._session)

    @property
    def app_state(self) -> AppStateRepository:
        assert self._session is not None, "UnitOfWork must be used as a context manager"
        return AppStateRepository(self._session)

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> UnitOfWork:
        self._session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session is None:
            return
        if exc_type is not None:
            self._session.rollback()
        self._session.close()
        self._session = None

    # ------------------------------------------------------------------
    # Explicit transaction control
    # ------------------------------------------------------------------

    def commit(self) -> None:
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
