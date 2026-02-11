"""
Processor Domain — Text Cleaner

Normalizes text formatting for TTS synthesis.

SINGLE RESPONSIBILITY: Normalize whitespace, remove emojis,
clean list markers. Does NOT handle content filtering (URLs,
images, HTML) — that's ContentFilter's job.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


class TextCleaner:
    """
    Normalizes raw text formatting for TTS synthesis.

    Handles whitespace normalization, emoji removal, and list marker
    cleanup. Content filtering (URLs, images, HTML, markdown) is
    handled separately by ContentFilter for clear SRP separation.
    """

    # Pre-compiled regex patterns for performance
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
    _MULTIPLE_SPACES = re.compile(r"[ \t]+")
    _MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
    _BULLET_PATTERN = re.compile(r"^\s*[-•·]\s+", re.MULTILINE)
    _NUMBERED_LIST = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)

    def clean(self, text: str) -> str:
        """
        Normalize raw text formatting for TTS.

        Args:
            text: Input text (already content-filtered or raw).

        Returns:
            Normalized text, or empty string if nothing remains.
        """
        if not text or not text.strip():
            return ""

        original_length = len(text)

        # 1. Remove emojis
        text = self._EMOJI_PATTERN.sub("", text)

        # 2. Clean up list markers (but keep the text content)
        text = self._BULLET_PATTERN.sub("", text)
        text = self._NUMBERED_LIST.sub("", text)

        # 3. Normalize whitespace
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
