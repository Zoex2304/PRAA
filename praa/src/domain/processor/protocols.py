"""
Processor Domain — Protocols (Interface Segregation)

Defines contracts for text processing sub-components.
Each sub-component has its own minimal protocol (ISP).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.infrastructure.events import DetectedLanguage


@runtime_checkable
class ITextCleaner(Protocol):
    """Contract for text cleaning implementations."""

    def clean(self, text: str) -> str:
        """
        Clean raw text by removing noise (URLs, emojis, special chars).

        Args:
            text: Raw input text.

        Returns:
            Cleaned text suitable for TTS.
        """
        ...


@runtime_checkable
class ILanguageDetector(Protocol):
    """Contract for language detection implementations."""

    def detect(self, text: str) -> DetectedLanguage:
        """
        Detect the primary language of the text.

        Args:
            text: Input text to analyze.

        Returns:
            Detected language enum value.
        """
        ...


@runtime_checkable
class ITextChunker(Protocol):
    """Contract for text chunking implementations."""

    def chunk(self, text: str, max_length: int) -> list[str]:
        """
        Split text into chunks suitable for TTS synthesis.

        Args:
            text: Input text to split.
            max_length: Maximum character count per chunk.

        Returns:
            List of text chunks.
        """
        ...


@runtime_checkable
class IContentFilter(Protocol):
    """Contract for content filtering implementations."""

    def filter(self, text: str) -> str:
        """
        Remove non-speech content (images, media, URLs, HTML).

        Args:
            text: Input text that may contain non-speech artifacts.

        Returns:
            Text with non-speech content removed.
        """
        ...

