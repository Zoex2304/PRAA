from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(
        String, nullable=False, server_default="CURRENT_TIMESTAMP"
    )
    text_content: Mapped[str] = mapped_column(String, nullable=False)
    audio_paths: Mapped[str] = mapped_column(String, nullable=False)
    word_boundaries: Mapped[str | None] = mapped_column(String, nullable=True)
    config_snapshot: Mapped[str | None] = mapped_column(String, nullable=True)
    source_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default="USER_BLOCK"
    )


class AppStateRecord(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
