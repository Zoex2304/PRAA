
from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.infrastructure.events import DetectedLanguage


@runtime_checkable
class ITextCleaner(Protocol):

    def clean(self, text: str) -> str:
        ...


@runtime_checkable
class ILanguageDetector(Protocol):

    def detect(self, text: str) -> DetectedLanguage:
        ...


@runtime_checkable
class ITextChunker(Protocol):

    def chunk(self, text: str, max_length: int) -> list[str]:
        ...


@runtime_checkable
class IContentFilter(Protocol):

    def filter(self, text: str) -> str:
        ...

