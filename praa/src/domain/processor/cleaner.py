"""
Processor Domain — Regex-based Text Cleaner

Strips URLs, emojis, markdown symbols, and excessive whitespace.
Pure function class with no side effects — easily testable.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


class TextCleaner:
    """
    Cleans raw text to make it suitable for TTS synthesis.

    Removes noise that would sound awkward or confusing when read aloud,
    while preserving the semantic content of the text.
    """

    # Pre-compiled regex patterns for performance
    _URL_PATTERN = re.compile(
        r"https?://[^\s<>\"{}|\\^`\[\]]+", re.IGNORECASE
    )
    _EMAIL_PATTERN = re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE
    )
    _EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & pictographs
        "\U0001F680-\U0001F6FF"  # Transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"  # Enclosed characters
        "\U0001F900-\U0001F9FF"  # Supplemental symbols
        "\U0001FA00-\U0001FA6F"  # Chess symbols
        "\U0001FA70-\U0001FAFF"  # Symbols extended-A
        "]+",
        re.UNICODE,
    )
    _MARKDOWN_PATTERN = re.compile(
        r"[*_~`#>\[\]!|]+"
    )
    _MULTIPLE_SPACES = re.compile(r"[ \t]+")
    _MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
    _BULLET_PATTERN = re.compile(r"^\s*[-•·]\s+", re.MULTILINE)
    _NUMBERED_LIST = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)

    def clean(self, text: str) -> str:
        """
        Clean raw text by removing noise unsuitable for TTS.

        Processing order matters — URLs must be removed before
        markdown stripping to avoid partial URL fragments.

        Args:
            text: Raw input text.

        Returns:
            Cleaned text, or empty string if nothing remains.
        """
        if not text or not text.strip():
            return ""

        original_length = len(text)

        # 1. Remove URLs and emails first (they contain special chars)
        text = self._URL_PATTERN.sub("", text)
        text = self._EMAIL_PATTERN.sub("", text)

        # 2. Remove emojis
        text = self._EMOJI_PATTERN.sub("", text)

        # 3. Remove markdown formatting symbols
        text = self._MARKDOWN_PATTERN.sub("", text)

        # 4. Clean up list markers (but keep the text content)
        text = self._BULLET_PATTERN.sub("", text)
        text = self._NUMBERED_LIST.sub("", text)

        # 5. Normalize whitespace
        text = self._MULTIPLE_SPACES.sub(" ", text)
        text = self._MULTIPLE_NEWLINES.sub("\n\n", text)
        text = text.strip()

        if text:
            logger.debug(
                "Text cleaned: %d → %d characters",
                original_length,
                len(text),
            )
        else:
            logger.debug("Text cleaned to empty string")

        return text
